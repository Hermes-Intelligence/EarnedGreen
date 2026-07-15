#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from pypdf import PdfReader

HERE = Path(__file__).resolve().parent
CANDIDATE = HERE.parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((CANDIDATE / "run-manifest.json").read_text(encoding="utf-8-sig"))
    failures = []
    for relative in manifest["required_artifacts"] + ["promotion/manifest.json"]:
        if not (CANDIDATE / relative).is_file():
            failures.append(f"missing artifact: {relative}")
    snapshot = json.loads((CANDIDATE / "source-registry-snapshot.json").read_text(encoding="utf-8-sig"))
    source_ids = {row["id"] for row in snapshot["sources"]}
    required_claim_fields = {"id","statement","topic","applicability","sources","research_verdict","verification_verdict","confidence","expires_at"}
    for filename in ("claims.json", "rejected-claims.json"):
        for row in json.loads((CANDIDATE / filename).read_text(encoding="utf-8-sig")):
            missing = required_claim_fields - set(row)
            if missing:
                failures.append(f"{filename}:{row.get('id')} missing {sorted(missing)}")
            unknown = set(row.get("sources", [])) - source_ids
            if unknown:
                failures.append(f"{filename}:{row.get('id')} unknown sources {sorted(unknown)}")
    promotion = json.loads((CANDIDATE / "promotion/manifest.json").read_text(encoding="utf-8-sig"))
    for row in promotion["files"]:
        source = CANDIDATE / row["source"]
        if not source.is_file() or sha(source) != row["after_sha256"]:
            failures.append(f"promotion source/hash invalid: {row['source']}")
    pdf = PdfReader(CANDIDATE / "report.pdf")
    links = []
    for page in pdf.pages:
        for annotation in page.get("/Annots", []):
            action = annotation.get_object().get("/A")
            if action and action.get("/URI"):
                links.append(action.get("/URI"))
    if len(set(links)) < 10:
        failures.append("report PDF has fewer than 10 unique clickable source links")
    eval_summary = json.loads((CANDIDATE / "evidence/candidate-eval-summary.json").read_text(encoding="utf-8-sig"))
    if eval_summary.get("verdict") != "PASS" or eval_summary.get("failed") != 0 or eval_summary.get("provider_calls") != 0:
        failures.append("candidate eval summary is not a zero-provider PASS")
    result = {
        "schema_version": 2,
        "verdict": "PASS" if not failures else "FAIL",
        "required_artifacts": len(manifest["required_artifacts"]) + 1,
        "claims": len(json.loads((CANDIDATE / "claims.json").read_text(encoding="utf-8-sig"))),
        "rejected_claims": len(json.loads((CANDIDATE / "rejected-claims.json").read_text(encoding="utf-8-sig"))),
        "promotion_files": len(promotion["files"]),
        "pdf_pages": len(pdf.pages),
        "pdf_unique_links": len(set(links)),
        "provider_calls": 0,
        "failures": failures,
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if not failures else 1)


if __name__ == "__main__":
    main()
