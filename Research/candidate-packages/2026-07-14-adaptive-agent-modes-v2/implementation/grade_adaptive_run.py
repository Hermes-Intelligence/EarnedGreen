#!/usr/bin/env python3
"""Host-only grader for adaptive arms, including the agent-visible completion gate."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from context_telemetry import analyze_run
from fixture_admission import resolve_command


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def run_json(command: list[str], cwd: Path) -> tuple[int, dict | None, str]:
    completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True,
                               encoding="utf-8", errors="replace", timeout=120)
    output = (completed.stdout + "\n" + completed.stderr).strip()
    parsed = None
    for line in reversed(output.splitlines()):
        try:
            parsed = json.loads(line)
            break
        except json.JSONDecodeError:
            pass
    return completed.returncode, parsed, output[-4000:]


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    args = parser.parse_args()
    run = args.run.resolve()
    repo = args.repo.resolve()
    manifest_path = run / "run-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    workspace = run / manifest["workspace"]
    protected_changed = []
    for row in manifest["protected_initial_files"]:
        path = workspace / row["path"]
        if not path.is_file() or sha(path) != row["sha256"]:
            protected_changed.append(row["path"])
    public_exit, _, public_output = run_json(resolve_command(list(manifest["public_test"]), sys.executable), workspace)
    grader = repo / manifest["central_hidden_grader"]
    hidden_exit, hidden, hidden_output = run_json([sys.executable, str(grader), str(workspace)], workspace)
    gate_result = None
    if manifest["arm"] != "vanilla":
        gate_path = workspace / ".agentic/pre-submit-result.json"
        if gate_path.is_file():
            gate_result = json.loads(gate_path.read_text(encoding="utf-8-sig"))
    enforcement_pass = not protected_changed and (manifest["arm"] == "vanilla" or bool(gate_result and gate_result.get("verdict") == "PASS" and gate_result.get("completion_allowed")))
    execution_path = run / "provider-execution.json"
    execution = json.loads(execution_path.read_text(encoding="utf-8-sig")) if execution_path.is_file() else {}
    hidden_valid = bool(hidden and isinstance(hidden.get("score"), (int, float)) and 0 <= hidden["score"] <= 100)
    quality = public_exit == 0 and hidden_exit == 0 and bool(hidden and hidden.get("passed")) and enforcement_pass
    initial = {row["path"]: row["sha256"] for row in manifest["initial_files"]}
    changed = []
    for path in workspace.rglob("*"):
        if not path.is_file() or ".agentic" in path.parts or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        rel = path.relative_to(workspace).as_posix()
        if initial.get(rel) != sha(path):
            changed.append(rel)
    token_usage = execution.get("token_usage") or {"total_observed_tokens":0,"source":"not-reported"}
    record = {
        "schema_version": 3,
        "case_id": manifest["fixture"], "arm": manifest["arm"], "provider": manifest["provider"],
        "requested_profile": manifest["requested_model_profile"],
        "actual_model": execution.get("actual_model", "unresolved-provider-default"), "effort": execution.get("effort"),
        "token_usage": token_usage, "tokens": token_usage.get("total_observed_tokens", 0),
        "monetary_cost": execution.get("monetary_cost", {"amount_usd":None,"basis":"not-reported"}),
        "started_at": execution.get("started_at", manifest["prepared_at"]), "finished_at": datetime.now(timezone.utc).isoformat(),
        "outcome_valid": hidden_valid and not protected_changed,
        "quality_passed": quality, "changed_files": sorted(changed), "protected_files_changed": protected_changed,
        "public_tests": {"passed":public_exit == 0,"exit_code":public_exit,"output":public_output},
        "grader": hidden or {"passed":False,"score":0,"diagnostic":hidden_output},
        "enforcement_passed": enforcement_pass, "pre_submit_gate": gate_result,
    }
    (run / "run-record.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    catalog = json.loads((Path(__file__).resolve().parent / "router-catalog.json").read_text(encoding="utf-8-sig"))
    markers = {row["id"]: row.get("outcome_markers", []) for row in catalog["modules"]}
    telemetry = analyze_run(run, markers)
    (run / "context-usage.json").write_text(json.dumps(telemetry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    record["context_usage"] = "context-usage.json"
    (run / "run-record.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest["status"] = "graded"
    manifest["actual_model"] = record["actual_model"]
    manifest["effort"] = record["effort"]
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False, indent=2))
    raise SystemExit(0 if record["outcome_valid"] else 1)


if __name__ == "__main__":
    main()
