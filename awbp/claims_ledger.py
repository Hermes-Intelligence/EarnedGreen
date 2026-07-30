#!/usr/bin/env python3
"""Claims->rules traceability validator.

Validates claims-rules-map.json, the machine-readable map linking each material
rule (Core runtime items, knowledge modules, policies, modes.json capabilities
and thresholds, key benchmark-protocol rules) to the research claim(s)/finding(s)
justifying it.

Verdicts:
- structural problems (unknown claim references, missing artifacts, malformed
  claims, inconsistent support labels, finding ids absent from the findings
  index, candidate-claim ids absent from claims.json) -> FAIL, exit 1.
- claims past their recheck/expiry date -> WARN (reported, exit 0): expiry must
  flag dependent rules, not break the suite, until the recheck loop is promoted.
- rules with support=unsupported -> reported count and id list. That list is a
  deliverable, not a failure: it is the honest inventory of rules with no
  research backing.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
VALID_SUPPORT = {"supported", "partial", "unsupported"}
VALID_CONFIDENCE = {"high", "medium", "low"}
REQUIRED_CLAIM_FIELDS = ("id", "kind", "statement", "source_url", "confidence", "recheck_at", "origin")
REQUIRED_RULE_FIELDS = ("id", "artifact", "rule", "justified_by", "support")


def repo_root() -> Path:
    for parent in (HERE, *HERE.parents):
        if (parent / "Runtime/stable/manifest.json").exists():
            return parent
    raise RuntimeError("AgenticWorkBestPractices root not found")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def parse_date(value: str) -> date | None:
    for fmt in ("%Y-%m-%d",):
        try:
            return datetime.strptime(value[:10], fmt).date()
        except (ValueError, TypeError):
            continue
    return None


def validate(map_path: Path, today: date | None = None) -> dict[str, Any]:
    repo = repo_root()
    today = today or date.today()
    errors: list[str] = []
    warnings: list[str] = []

    try:
        data = load_json(map_path)
    except (OSError, json.JSONDecodeError) as exc:
        return {"verdict": "FAIL", "errors": [f"claims-rules map unreadable: {exc}"], "warnings": []}

    claims = data.get("claims", [])
    rules = data.get("rules", [])
    if not claims:
        errors.append("map has no claims")
    if not rules:
        errors.append("map has no rules")

    # Findings index and candidate claim ledger for cross-checks. Promoted
    # layout (awbp/): the local copy wins when present, otherwise the
    # stable knowledge-base index is authoritative.
    index_path = HERE / "findings-index.json"
    if not index_path.exists():
        index_path = repo / "Research/knowledge-base/findings-index.json"
    finding_ids: set[str] = set()
    if index_path.exists():
        finding_ids = {row["id"] for row in load_json(index_path).get("findings", [])}
    else:
        errors.append(f"findings index not found: {index_path}")
    # The candidate-claim ledger travels with the research package. The map may
    # pin it explicitly (candidate_claims_ledger, repo-relative); otherwise the
    # candidate-local sibling is used. A missing ledger is a WARN outside a
    # candidate package: the promoted validator must stay runnable from Stable.
    declared_ledger = data.get("candidate_claims_ledger")
    candidate_claims_path = (repo / declared_ledger) if declared_ledger else (HERE.parent / "claims.json")
    candidate_claim_ids: set[str] = set()
    candidate_expiry: dict[str, str] = {}
    if candidate_claims_path.exists():
        for row in load_json(candidate_claims_path):
            candidate_claim_ids.add(row["id"])
            candidate_expiry[row["id"]] = row.get("expires_at", "")
    elif declared_ledger:
        errors.append(f"declared candidate claim ledger not found: {candidate_claims_path}")
    else:
        warnings.append(f"candidate claim ledger not found (kind=candidate-claim cross-check skipped): {candidate_claims_path}")

    claim_ids: set[str] = set()
    expired_claims: list[str] = []
    for claim in claims:
        cid = claim.get("id", "<missing-id>")
        if cid in claim_ids:
            errors.append(f"duplicate claim id: {cid}")
        claim_ids.add(cid)
        for field in REQUIRED_CLAIM_FIELDS:
            if not claim.get(field):
                errors.append(f"claim {cid}: missing field {field!r}")
        if claim.get("confidence") not in VALID_CONFIDENCE:
            errors.append(f"claim {cid}: invalid confidence {claim.get('confidence')!r}")
        recheck = parse_date(claim.get("recheck_at", ""))
        if recheck is None:
            errors.append(f"claim {cid}: unparseable recheck_at {claim.get('recheck_at')!r}")
        elif recheck < today:
            expired_claims.append(cid)
            warnings.append(f"claim {cid} is past its recheck date ({claim['recheck_at']})")
        kind = claim.get("kind")
        if kind == "finding" and finding_ids and cid not in finding_ids:
            errors.append(f"claim {cid} declares kind=finding but is absent from findings-index.json")
        if kind == "candidate-claim" and candidate_claim_ids and cid not in candidate_claim_ids:
            errors.append(f"claim {cid} declares kind=candidate-claim but is absent from claims.json")
        source_url = claim.get("source_url", "")
        if source_url and not source_url.startswith(("http://", "https://")):
            if not (repo / source_url).exists():
                errors.append(f"claim {cid}: repo-relative source path does not exist: {source_url}")

    rule_ids: set[str] = set()
    unsupported: list[str] = []
    partial: list[str] = []
    supported: list[str] = []
    rules_with_expired: list[str] = []
    links_total = 0
    for rule in rules:
        rid = rule.get("id", "<missing-id>")
        if rid in rule_ids:
            errors.append(f"duplicate rule id: {rid}")
        rule_ids.add(rid)
        for field in REQUIRED_RULE_FIELDS:
            if field not in rule:
                errors.append(f"rule {rid}: missing field {field!r}")
        artifact = rule.get("artifact", "")
        if artifact and not (repo / artifact).exists():
            errors.append(f"rule {rid}: artifact does not exist: {artifact}")
        support = rule.get("support")
        justified = rule.get("justified_by", [])
        links_total += len(justified)
        if support not in VALID_SUPPORT:
            errors.append(f"rule {rid}: invalid support {support!r}")
        if support in ("supported", "partial") and not justified:
            errors.append(f"rule {rid}: support={support} but justified_by is empty")
        if support == "unsupported":
            if justified:
                errors.append(f"rule {rid}: support=unsupported but justified_by is non-empty")
            if not rule.get("local_evidence"):
                errors.append(f"rule {rid}: unsupported rules must record local_evidence (what actually motivated the rule)")
            unsupported.append(rid)
        elif support == "partial":
            partial.append(rid)
        elif support == "supported":
            supported.append(rid)
        for cid in justified:
            if cid not in claim_ids:
                errors.append(f"rule {rid}: references unknown claim {cid}")
            elif cid in expired_claims:
                rules_with_expired.append(rid)
                warnings.append(f"rule {rid} depends on expired/recheck-due claim {cid}")

    result = {
        "schema_version": 1,
        "verdict": "FAIL" if errors else "PASS",
        "checked_at": today.isoformat(),
        "map": str(map_path),
        "claims_total": len(claims),
        "rules_total": len(rules),
        "links_total": links_total,
        "rules_supported": len(supported),
        "rules_partial": len(partial),
        "rules_unsupported": len(unsupported),
        "unsupported_rule_ids": sorted(unsupported),
        "expired_claims": sorted(set(expired_claims)),
        "rules_with_expired_claims": sorted(set(rules_with_expired)),
        "warnings": warnings,
        "errors": errors,
    }
    return result


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser()
    default_map = HERE / "claims-rules-map.json"
    if not default_map.exists():
        default_map = repo_root() / "Research/claims/claims-rules-map.json"
    parser.add_argument("--map", type=Path, default=default_map)
    parser.add_argument("--as-of", help="override today's date (YYYY-MM-DD) for expiry checks")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    today = parse_date(args.as_of) if args.as_of else None
    result = validate(args.map, today)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    raise SystemExit(0 if result["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
