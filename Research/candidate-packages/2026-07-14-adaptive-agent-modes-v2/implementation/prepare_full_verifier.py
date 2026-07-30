#!/usr/bin/env python3
"""Prepare a fresh independent-verifier call for the Full solution."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def inventory(workspace: Path) -> list[dict[str,str]]:
    return [{"path":p.relative_to(workspace).as_posix(),"sha256":sha(p)} for p in sorted(workspace.rglob("*")) if p.is_file() and ".agentic" not in p.parts]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--solution-run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--provider", required=True)
    args = parser.parse_args()
    source_manifest = json.loads((args.solution_run / "run-manifest.json").read_text(encoding="utf-8-sig"))
    source = args.solution_run / source_manifest["workspace"]
    workspace = args.output / "workspace"
    shutil.copytree(source, workspace)
    initial = inventory(workspace)
    report_path = workspace / ".agentic/independent-verification.json"
    if report_path.exists():
        report_path.unlink()
    prompt = """You are the fresh independent verifier for the critical arm. Do not modify product code, task.md, tests, or policy files. Read the public task, objective ledger, evidence ledger, diff and selected modules. Run public tests and adversarial checks derived only from the public contract. Write exactly .agentic/independent-verification.json as JSON with: {\"status\":\"PASS\" or \"FAIL\",\"verifier_profile\":\"adversarial-review\",\"findings\":[{\"id\":string (short slug),\"severity\":\"blocking\" or \"advisory\",\"claim\":string (one falsifiable sentence),\"suggested_check\":{\"command\":string} or null}],\"verification_runs\":[{\"command\":string,\"exit_code\":integer}]}. Findings MUST be machine-readable objects, never prose strings: each blocking finding is ingested into the solution's check suite and blocks completion until resolved with re-executable proof. PASS only if every objective is evidenced and no blocking issue remains. Hidden graders are unavailable and must not be searched for.\n"""
    (args.output / "prompt.txt").write_text(prompt, encoding="utf-8")
    manifest = {"schema_version":2,"run_id":args.output.name,"status":"prepared","fixture":source_manifest["fixture"],"arm":"critical-verifier","role":"independent-verifier","provider":args.provider,"workspace":"workspace","prepared_at":datetime.now(timezone.utc).isoformat(),"initial_files":initial,"source_solution_run":source_manifest["run_id"],"prompt_sha256":sha(args.output / "prompt.txt")}
    (args.output / "run-manifest.json").write_text(json.dumps(manifest,indent=2) + "\n",encoding="utf-8")
    print(json.dumps(manifest,indent=2))


if __name__ == "__main__":
    main()
