#!/usr/bin/env python3
"""Validate verifier independence, ingest its findings, and run the final gate.

Inert-verdict fix (F-2026-07-12-011): verifier findings are machine-readable
objects that get INGESTED into the solution's frozen check suite as blocking
checks. A finding stays failing until finding-resolutions.json names a proving
command the harness re-executes green, or an explicit owner waiver. The
verifier's verdict therefore has teeth: it changes what the gate requires.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import verification_loop


def normalize_findings(raw: list) -> list[dict]:
    """Machine-readable objects; legacy prose strings are wrapped as blocking."""
    rows = []
    for index, item in enumerate(raw):
        if isinstance(item, dict) and item.get("id"):
            rows.append({"id": str(item["id"]), "severity": item.get("severity", "blocking"),
                         "claim": str(item.get("claim", "")), "suggested_check": item.get("suggested_check")})
        else:
            rows.append({"id": f"legacy-{index + 1}", "severity": "blocking",
                         "claim": str(item), "suggested_check": None})
    return rows


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--solution-run", type=Path, required=True)
    parser.add_argument("--verifier-run", type=Path, required=True)
    args = parser.parse_args()
    solution_manifest = json.loads((args.solution_run / "run-manifest.json").read_text(encoding="utf-8-sig"))
    verifier_manifest = json.loads((args.verifier_run / "run-manifest.json").read_text(encoding="utf-8-sig"))
    solution = args.solution_run / solution_manifest["workspace"]
    verifier = args.verifier_run / verifier_manifest["workspace"]
    original = {row["path"]:row["sha256"] for row in verifier_manifest["initial_files"]}
    changed = []
    for path in verifier.rglob("*"):
        if path.is_file() and ".agentic" not in path.parts:
            rel = path.relative_to(verifier).as_posix()
            if original.get(rel) != sha(path):
                changed.append(rel)
    report_path = verifier / ".agentic/independent-verification.json"
    report = json.loads(report_path.read_text(encoding="utf-8-sig")) if report_path.is_file() else {"status":"FAIL","findings":["verifier report missing"],"verification_runs":[]}
    findings = normalize_findings(report.get("findings", []))
    valid = not changed and report.get("status") == "PASS" and report.get("verifier_profile") == "adversarial-review" and all(row.get("exit_code") == 0 for row in report.get("verification_runs", [])) and bool(report.get("verification_runs"))
    evidence_path = solution / ".agentic/evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8-sig"))
    evidence["independent_verification"] = {"status":"PASS" if valid else "FAIL","verifier_profile":"adversarial-review","evidence":report.get("verification_runs", []),"findings":findings,"verifier_run":verifier_manifest["run_id"],"product_files_changed_by_verifier":changed}
    evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # Ingest blocking findings into the solution's frozen check suite so the
    # gate re-run keeps failing until each is resolved with executable proof.
    blocking = [row for row in findings if row.get("severity") == "blocking"]
    ingested = None
    findings_path = solution / ".agentic/verifier-findings.json"
    if blocking:
        findings_path.write_text(json.dumps({"schema_version":1,"source":verifier_manifest["run_id"],"findings":blocking}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        suite_path = solution / ".agentic/check-suite.json"
        if suite_path.is_file():
            ingested = verification_loop.ingest_findings(suite_path, findings_path)
            # Ingestion legitimately re-freezes the suite (host-side, trusted):
            # keep the enforcement record in step so the gate's digest
            # comparison still catches AGENT tampering, not this ingest.
            enforcement_path = solution / ".agentic/enforcement.json"
            if ingested.get("verdict") == "ingested" and enforcement_path.is_file():
                enforcement = json.loads(enforcement_path.read_text(encoding="utf-8-sig"))
                suite = json.loads(suite_path.read_text(encoding="utf-8-sig"))
                enforcement["check_suite_freeze_sha256"] = suite["harness_freeze_sha256"]
                enforcement_path.write_text(json.dumps(enforcement, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    command = [sys.executable, str(solution / ".agentic/pre_submit_gate.py"), "--ledger", str(solution / ".agentic/objective-ledger.json"), "--evidence", str(evidence_path), "--workspace", str(solution), "--baseline", str(solution / ".agentic/baseline.json"), "--output", str(solution / ".agentic/pre-submit-result.json")]
    completed = subprocess.run(command, text=True, capture_output=True, encoding="utf-8", errors="replace", timeout=120)
    result = {"schema_version":3,"verifier_valid":valid,"blocking_findings":len(blocking),"findings_ingested":ingested,"product_files_changed":changed,"final_gate_exit":completed.returncode,"final_gate_passed":completed.returncode == 0,"verifier_run":verifier_manifest["run_id"]}
    (args.solution_run / "full-verification-result.json").write_text(json.dumps(result,indent=2) + "\n",encoding="utf-8")
    print(json.dumps(result,indent=2))
    raise SystemExit(0 if valid and completed.returncode == 0 else 1)


if __name__ == "__main__":
    main()
