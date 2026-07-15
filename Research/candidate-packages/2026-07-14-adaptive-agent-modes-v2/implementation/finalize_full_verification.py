#!/usr/bin/env python3
"""Validate verifier independence, attach its evidence, and run Full's final gate."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


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
    valid = not changed and report.get("status") == "PASS" and report.get("verifier_profile") == "adversarial-review" and all(row.get("exit_code") == 0 for row in report.get("verification_runs", [])) and bool(report.get("verification_runs"))
    evidence_path = solution / ".agentic/evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8-sig"))
    evidence["independent_verification"] = {"status":"PASS" if valid else "FAIL","verifier_profile":"adversarial-review","evidence":report.get("verification_runs", []),"findings":report.get("findings", []),"verifier_run":verifier_manifest["run_id"],"product_files_changed_by_verifier":changed}
    evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    command = [sys.executable, str(solution / ".agentic/pre_submit_gate.py"), "--ledger", str(solution / ".agentic/objective-ledger.json"), "--evidence", str(evidence_path), "--workspace", str(solution), "--baseline", str(solution / ".agentic/baseline.json"), "--output", str(solution / ".agentic/pre-submit-result.json")]
    completed = subprocess.run(command, text=True, capture_output=True, encoding="utf-8", errors="replace", timeout=60)
    result = {"schema_version":2,"verifier_valid":valid,"product_files_changed":changed,"final_gate_exit":completed.returncode,"final_gate_passed":completed.returncode == 0,"verifier_run":verifier_manifest["run_id"]}
    (args.solution_run / "full-verification-result.json").write_text(json.dumps(result,indent=2) + "\n",encoding="utf-8")
    print(json.dumps(result,indent=2))
    raise SystemExit(0 if valid and completed.returncode == 0 else 1)


if __name__ == "__main__":
    main()
