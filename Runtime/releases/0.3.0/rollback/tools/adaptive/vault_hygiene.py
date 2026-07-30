#!/usr/bin/env python3
"""Vault hygiene: a zero-provider, REPORT-ONLY scan of the repo's knowledge surfaces.

Governance-adapted Obsidian-vault-maintenance kernel: a periodic pass hunting
contradictions, staleness, broken references and orphans across Core/, the
Router catalog, Research/knowledge-base, Research/sources, workstreams/, Models/
and the candidate package docs. It NEVER deletes or edits anything: the output
is a dated JSON + Markdown hygiene report (review-before-commit always). A
future promoted /weekly-hygiene command runs this and hands the report to the
owner.

Checks:
 (a) cross-reference integrity - files referenced by manifests/catalogs/markdown
     links that do not exist; tools that exist but no document mentions.
 (b) staleness - expiry/recheck dates past due (model catalog expires_at, source
     registry next_check, workstream updated_at older than N days while active,
     claims past expiry/recheck).
 (c) contradiction CANDIDATES - cheap targeted heuristics only (conflicting
     status for the same requirement id across ledgers; docs still asserting v1
     research-workflow artifacts where the v2 runbook exists). These are
     candidates for HUMAN review, not verdicts; no NLP is attempted.
 (d) orphans - knowledge modules in no router catalog and linked by no scanned
     doc; findings never linked in the claims-rules map; workstream files
     missing from INDEX.md.

Gate semantics (--gate-package): broken cross-references INSIDE the candidate
package fail the suite (exit 1); every repo-level finding is informational.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CANDIDATE = HERE.parent

MD_LINK = re.compile(r"\[[^\]]*\]\(([^)#\s]+)(?:#[^)]*)?\)")
V1_ARTIFACTS = ("research-workflow.js", "engine/state.json")
# Docs that legitimately DESCRIBE the v1 artifacts as deprecated/reference.
V1_MENTION_EXEMPT_MARKERS = ("v1", "legacy", "historical", "reference-only", "deprecated", "not** part", "not part")


def repo_root() -> Path:
    for parent in (HERE, *HERE.parents):
        if (parent / "Runtime/stable/manifest.json").exists():
            return parent
    raise RuntimeError("AgenticWorkBestPractices root not found")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def policy_path(local_name: str, stable_rel: str, repo: Path) -> Path:
    """Candidate-local artifact wins when present; otherwise the promoted Stable copy."""
    local = HERE / local_name
    return local if local.exists() else repo / stable_rel


def parse_day(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
        except ValueError:
            return None


def scan_markdown_files(repo: Path) -> list[Path]:
    """Knowledge-surface markdown docs to link-check (bounded, deterministic)."""
    docs: list[Path] = []
    for pattern in ("*.md", "Claude/*.md", "Codex/*.md", "Core/**/*.md", "Router/**/*.md",
                    "Models/*.md", "workstreams/*.md", "Research/knowledge-base/*.md",
                    "Research/sources/*.md", "Research/engine/*.md", "Objectives/**/*.md"):
        docs.extend(sorted(repo.glob(pattern)))
    docs.extend(sorted(CANDIDATE.glob("*.md")))
    docs.extend(sorted((CANDIDATE / "implementation").glob("*.md")))
    return [doc for doc in dict.fromkeys(docs) if doc.is_file()]


def check_cross_references(repo: Path) -> dict[str, Any]:
    broken: list[dict[str, str]] = []
    package_broken: list[dict[str, str]] = []

    def record(source: Path, target: str, kind: str) -> None:
        row = {"source": source.as_posix().replace(repo.as_posix() + "/", ""), "target": target, "kind": kind}
        broken.append(row)
        if CANDIDATE in source.parents or source == CANDIDATE:
            package_broken.append(row)

    # Stable manifest references.
    manifest_path = repo / "Runtime/stable/manifest.json"
    manifest = load_json(manifest_path)
    refs = [manifest.get("core"), manifest.get("objective"), manifest.get("router_catalog"),
            *(manifest.get("platform_adapters") or {}).values()]
    for ref in refs:
        if ref and not (repo / ref).exists():
            record(manifest_path, ref, "manifest-reference")

    # Router catalogs (stable + candidate) -> module paths.
    for catalog_path, base in ((repo / "Router/catalog/modules.json", repo),
                               (policy_path("router-catalog.json", "Router/catalog/adaptive-modules.json", repo), None)):
        if not catalog_path.exists():
            record(catalog_path.parent, catalog_path.name, "catalog-missing")
            continue
        for module in load_json(catalog_path).get("modules", []):
            rel = module.get("path", "")
            target = (CANDIDATE / rel) if (base is None and rel.startswith("implementation/")) else (repo / rel)
            if rel and not target.exists():
                record(catalog_path, rel, "catalog-module-path")

    # Markdown relative links.
    for doc in scan_markdown_files(repo):
        text = doc.read_text(encoding="utf-8-sig", errors="replace")
        for match in MD_LINK.finditer(text):
            target = match.group(1).strip()
            if target.startswith(("http://", "https://", "mailto:", "<")) or "://" in target:
                continue
            resolved = (doc.parent / target)
            if not resolved.exists() and not (repo / target).exists():
                record(doc, target, "markdown-link")

    # Claims-rules map artifacts + findings index corpus files.
    for map_name, stable_rel in (("claims-rules-map.json", "Research/claims/claims-rules-map.json"),
                                 ("findings-index.json", "Research/knowledge-base/findings-index.json")):
        map_path = policy_path(map_name, stable_rel, repo)
        if not map_path.exists():
            record(HERE, map_name, "package-artifact-missing")
            continue
        data = load_json(map_path)
        for rule in data.get("rules", []):
            if rule.get("artifact") and not (repo / rule["artifact"]).exists():
                record(map_path, rule["artifact"], "claims-map-artifact")
        for corpus in data.get("corpus", []):
            if not (repo / corpus).exists():
                record(map_path, corpus, "findings-index-corpus")

    # Tools that exist but no scanned doc mentions.
    mentioned = ""
    for doc in scan_markdown_files(repo):
        mentioned += doc.read_text(encoding="utf-8-sig", errors="replace")
    unmentioned_tools = [tool.name for tool in sorted((repo / "tools").glob("*.ps1"))
                         if tool.name not in mentioned]

    return {"broken_references": broken, "package_broken_references": package_broken,
            "unmentioned_tools": unmentioned_tools,
            "broken_count": len(broken), "package_broken_count": len(package_broken)}


def check_staleness(repo: Path, today: date, max_workstream_age_days: int) -> dict[str, Any]:
    stale: list[dict[str, Any]] = []

    providers_path = repo / "Models/providers.json"
    if providers_path.exists():
        providers = load_json(providers_path)
        expires = parse_day(providers.get("expires_at"))
        if expires and expires < today:
            stale.append({"artifact": "Models/providers.json", "field": "expires_at",
                          "value": providers.get("expires_at"), "issue": "model catalog expired"})

    registry_path = repo / "Research/sources/registry.json"
    if registry_path.exists():
        for source in load_json(registry_path).get("sources", []):
            due = parse_day(source.get("next_check"))
            if source.get("status") == "active" and due and due < today:
                stale.append({"artifact": "Research/sources/registry.json", "field": f"sources[{source['id']}].next_check",
                              "value": source.get("next_check"), "issue": "source recheck past due"})

    current_path = repo / "workstreams/current.json"
    if current_path.exists():
        current = load_json(current_path)
        updated = parse_day(current.get("updated_at"))
        if current.get("status") in ("in_progress", "active") and updated and (today - updated).days > max_workstream_age_days:
            stale.append({"artifact": "workstreams/current.json", "field": "updated_at",
                          "value": current.get("updated_at"),
                          "issue": f"active workstream not updated for more than {max_workstream_age_days} days"})

    claims_path = CANDIDATE / "claims.json"
    if claims_path.exists():
        for claim in load_json(claims_path):
            expires = parse_day(claim.get("expires_at"))
            if expires and expires < today:
                stale.append({"artifact": claims_path.name, "field": f"{claim['id']}.expires_at",
                              "value": claim.get("expires_at"), "issue": "candidate claim expired"})

    map_path = policy_path("claims-rules-map.json", "Research/claims/claims-rules-map.json", repo)
    if map_path.exists():
        for claim in load_json(map_path).get("claims", []):
            recheck = parse_day(claim.get("recheck_at"))
            if recheck and recheck < today:
                stale.append({"artifact": "implementation/claims-rules-map.json", "field": f"{claim['id']}.recheck_at",
                              "value": claim.get("recheck_at"), "issue": "harvested claim past recheck date"})

    return {"stale_items": stale, "stale_count": len(stale)}


def check_contradiction_candidates(repo: Path) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []

    # Heuristic 1: same requirement id with different status across the objective
    # ledger and the workstream resume pointer.
    objective_status: dict[str, str] = {}
    for obj_path in sorted((repo / "Objectives/active").glob("*.json")):
        data = load_json(obj_path)
        for pillar in data.get("pillars", []):
            for req in pillar.get("requirements", []):
                objective_status[req["id"]] = req.get("status", "")
    current_path = repo / "workstreams/current.json"
    if current_path.exists():
        for req in load_json(current_path).get("requirements", []):
            obj = objective_status.get(req["id"])
            if obj and req.get("status") and obj != req["status"]:
                candidates.append({
                    "kind": "requirement-status-conflict",
                    "artifact": req["id"],
                    "detail": f"Objectives/active says {obj!r}, workstreams/current.json says {req['status']!r}",
                    "note": "candidate for human review: one ledger may simply lag the other",
                })

    # Heuristic 2: docs still asserting v1 research-workflow artifacts where the
    # v2 candidate-only runbook exists (targeted grep, not NLP).
    brief = repo / "Research/engine/research-brief.md"
    if brief.exists():
        for doc in scan_markdown_files(repo):
            if doc == brief:
                continue
            text = doc.read_text(encoding="utf-8-sig", errors="replace")
            for artifact in V1_ARTIFACTS:
                for line in text.splitlines():
                    if artifact in line and not any(marker in line.lower() for marker in V1_MENTION_EXEMPT_MARKERS):
                        candidates.append({
                            "kind": "v1-workflow-assertion",
                            "artifact": doc.as_posix().replace(repo.as_posix() + "/", ""),
                            "detail": f"mentions {artifact} without a v1/legacy/deprecated marker while the v2 runbook exists",
                            "note": "candidate for human review",
                        })
                        break

    # Heuristic 3: conflicting status fields for the same candidate package
    # (run-manifest.json vs handoff.json) - flag only clear disagreement shapes.
    for pkg in sorted((repo / "Research/candidate-packages").iterdir()):
        if not pkg.is_dir():
            continue
        statuses: dict[str, str] = {}
        for name in ("run-manifest.json", "handoff.json"):
            path = pkg / name
            if path.exists():
                value = load_json(path).get("status")
                if value:
                    statuses[name] = str(value)
        if len(statuses) == 2:
            a, b = statuses["run-manifest.json"], statuses["handoff.json"]
            if a != b and not (a in b or b in a):
                candidates.append({
                    "kind": "package-status-divergence",
                    "artifact": pkg.name,
                    "detail": f"run-manifest.json status={a!r} vs handoff.json status={b!r}",
                    "note": "candidate for human review: statuses may describe different lifecycle stages",
                })

    return {"contradiction_candidates": candidates, "candidate_count": len(candidates),
            "limits": "targeted heuristics only; semantic contradictions (e.g. a stale count in prose) are NOT detected"}


def check_orphans(repo: Path) -> dict[str, Any]:
    orphans: list[dict[str, Any]] = []

    # Knowledge modules/policies in no catalog and linked by no scanned doc.
    catalog_paths: set[str] = set()
    for catalog_path in (repo / "Router/catalog/modules.json",
                         policy_path("router-catalog.json", "Router/catalog/adaptive-modules.json", repo)):
        if catalog_path.exists():
            for module in load_json(catalog_path).get("modules", []):
                catalog_paths.add(module.get("path", ""))
    all_docs_text = ""
    for doc in scan_markdown_files(repo):
        all_docs_text += doc.read_text(encoding="utf-8-sig", errors="replace")
    for module_file in sorted((repo / "Core/knowledge-modules").glob("*.md")) + sorted((repo / "Core/policies").glob("*.md")):
        rel = module_file.relative_to(repo).as_posix()
        if rel not in catalog_paths and module_file.name not in all_docs_text:
            orphans.append({"kind": "uncataloged-knowledge-module", "artifact": rel,
                            "detail": "in no router catalog and mentioned by no scanned doc"})

    # Findings never linked in the claims-rules map.
    index_path = policy_path("findings-index.json", "Research/knowledge-base/findings-index.json", repo)
    map_path = policy_path("claims-rules-map.json", "Research/claims/claims-rules-map.json", repo)
    if index_path.exists() and map_path.exists():
        linked: set[str] = set()
        for rule in load_json(map_path).get("rules", []):
            linked.update(rule.get("justified_by", []))
        for finding in load_json(index_path).get("findings", []):
            if finding["id"] not in linked:
                orphans.append({"kind": "unlinked-finding", "artifact": finding["id"],
                                "detail": "in findings-index.json but justifies no rule in claims-rules-map.json"})

    # Workstream files missing from INDEX.md (index drift).
    index_md = repo / "workstreams/INDEX.md"
    if index_md.exists():
        index_text = index_md.read_text(encoding="utf-8-sig", errors="replace")
        for ws in sorted((repo / "workstreams").glob("*.md")):
            if ws.name in ("INDEX.md", "README.md"):
                continue
            if ws.name not in index_text:
                orphans.append({"kind": "workstream-index-drift", "artifact": f"workstreams/{ws.name}",
                                "detail": "workstream file not listed in workstreams/INDEX.md"})

    return {"orphans": orphans, "orphan_count": len(orphans)}


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Vault Hygiene Report - {report['generated_at']}",
        "",
        "Report-only scan; nothing was modified. Every repo-level finding is informational",
        "and awaits human review. Package-level broken references gate the candidate suite.",
        "",
        "## Headline",
        "",
        f"- Broken cross-references: **{report['cross_references']['broken_count']}**"
        f" (candidate package: {report['cross_references']['package_broken_count']})",
        f"- Unmentioned tools: **{len(report['cross_references']['unmentioned_tools'])}**",
        f"- Stale items: **{report['staleness']['stale_count']}**",
        f"- Contradiction candidates (human review): **{report['contradictions']['candidate_count']}**",
        f"- Orphans: **{report['orphans']['orphan_count']}**",
        "",
    ]
    if report["cross_references"]["broken_references"]:
        lines += ["## Broken cross-references", ""]
        for row in report["cross_references"]["broken_references"]:
            lines.append(f"- `{row['source']}` -> `{row['target']}` ({row['kind']})")
        lines.append("")
    if report["cross_references"]["unmentioned_tools"]:
        lines += ["## Tools no scanned doc mentions", ""]
        for name in report["cross_references"]["unmentioned_tools"]:
            lines.append(f"- `tools/{name}`")
        lines.append("")
    if report["staleness"]["stale_items"]:
        lines += ["## Stale", ""]
        for row in report["staleness"]["stale_items"]:
            lines.append(f"- `{row['artifact']}` {row['field']} = {row['value']}: {row['issue']}")
        lines.append("")
    if report["contradictions"]["contradiction_candidates"]:
        lines += ["## Contradiction candidates (human review required)", ""]
        for row in report["contradictions"]["contradiction_candidates"]:
            lines.append(f"- [{row['kind']}] `{row['artifact']}`: {row['detail']}")
        lines.append("")
    if report["orphans"]["orphans"]:
        lines += ["## Orphans", ""]
        for row in report["orphans"]["orphans"]:
            lines.append(f"- [{row['kind']}] `{row['artifact']}`: {row['detail']}")
        lines.append("")
    lines += ["## Honest limits", "",
              "- Contradiction detection is heuristic grep, labeled candidates only; semantic",
              "  contradictions (a stale count or claim inside prose) are not detected.",
              "- Markdown scanning covers the declared knowledge surfaces, not every file.",
              "- Workstream staleness reads structured `updated_at` fields only; prose logs",
              "  without dates are not aged.", ""]
    return "\n".join(lines)


def run_scan(today: date, max_workstream_age_days: int) -> dict[str, Any]:
    repo = repo_root()
    return {
        "schema_version": 1,
        "generated_at": today.isoformat(),
        "mode": "report-only",
        "modified_files": [],
        "cross_references": check_cross_references(repo),
        "staleness": check_staleness(repo, today, max_workstream_age_days),
        "contradictions": check_contradiction_candidates(repo),
        "orphans": check_orphans(repo),
    }


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser()
    # Candidate layout keeps writing into the package's evidence/; the promoted
    # copy (tools/adaptive/) defaults to the repo's hygiene output area instead
    # of inventing a tools/evidence directory.
    default_output = CANDIDATE / "evidence"
    if not (CANDIDATE / "run-manifest.json").exists():
        default_output = repo_root() / "Research Outputs" / "hygiene"
    parser.add_argument("--output-dir", type=Path, default=default_output)
    parser.add_argument("--as-of", help="override today's date (YYYY-MM-DD)")
    parser.add_argument("--max-workstream-age-days", type=int, default=7)
    parser.add_argument("--gate-package", action="store_true",
                        help="exit 1 when the candidate package itself has broken cross-references")
    args = parser.parse_args()
    today = datetime.strptime(args.as_of, "%Y-%m-%d").date() if args.as_of else datetime.now(timezone.utc).date()
    report = run_scan(today, args.max_workstream_age_days)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = today.strftime("%Y%m%d")
    json_path = args.output_dir / f"vault-hygiene-report-{stamp}.json"
    md_path = args.output_dir / f"vault-hygiene-report-{stamp}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({
        "verdict": "PASS" if not (args.gate_package and report["cross_references"]["package_broken_count"]) else "FAIL",
        "report_json": str(json_path),
        "report_markdown": str(md_path),
        "broken_references": report["cross_references"]["broken_count"],
        "package_broken_references": report["cross_references"]["package_broken_count"],
        "unmentioned_tools": len(report["cross_references"]["unmentioned_tools"]),
        "stale_items": report["staleness"]["stale_count"],
        "contradiction_candidates": report["contradictions"]["candidate_count"],
        "orphans": report["orphans"]["orphan_count"],
    }, ensure_ascii=False, indent=2))
    if args.gate_package and report["cross_references"]["package_broken_count"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
