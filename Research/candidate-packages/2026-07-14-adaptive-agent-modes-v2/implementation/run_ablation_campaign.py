#!/usr/bin/env python3
"""Sequential, approval-locked runner for five solutions plus the Full verifier."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent


def repo_root() -> Path:
    for parent in HERE.parents:
        if (parent / "Runtime/stable/manifest.json").exists():
            return parent
    raise RuntimeError("repository root not found")


REPO = repo_root()


def save(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def call(command: list[str], timeout: int = 2400) -> int:
    completed = subprocess.run(command, cwd=REPO, timeout=timeout)
    return completed.returncode


def invoke_provider(run_id: str, campaign: dict) -> int:
    provider = campaign["provider_snapshot"]["provider"]
    return call([
        "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(REPO / "Evals/adapters/providers/invoke-agenticbench.ps1"),
        "-Run", run_id, "-Provider", provider["id"], "-Model", provider["model"], "-Effort", provider["effort"],
        "-MaxTurns", str(campaign["loop"]["max_turns_per_call"]), "-MaxWallMinutes", str(campaign["loop"]["max_wall_minutes_per_call"]), "-Execute"
    ])


def prepare_solution(campaign: dict, entry: dict) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S%f")[:-3]
    run_id = f"{stamp}-{campaign['fixture']}-{entry['arm']}-t1"
    run = REPO / "Evals/runs" / run_id
    command = [sys.executable, str(HERE / "prepare_adaptive_run.py"), "--fixture", campaign["fixture"], "--arm", entry["arm"], "--output", str(run), "--provider", campaign["provider_snapshot"]["provider"]["id"], "--trial", "1"]
    if entry["arm"] == "full":
        command += ["--approved-by", campaign["approval"]["approved_by"]]
    if call(command, 120) != 0:
        raise RuntimeError("solution preparation failed")
    entry["run_id"] = run_id
    entry["status"] = "prepared"
    return run


def prepare_verifier(campaign: dict, full_run: Path, entry: dict) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S%f")[:-3]
    run_id = f"{stamp}-{campaign['fixture']}-full-verifier-t1"
    run = REPO / "Evals/runs" / run_id
    if call([sys.executable, str(HERE / "prepare_full_verifier.py"), "--solution-run", str(full_run), "--output", str(run), "--provider", campaign["provider_snapshot"]["provider"]["id"]], 120) != 0:
        raise RuntimeError("verifier preparation failed")
    entry["run_id"] = run_id
    entry["status"] = "prepared"
    return run


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--max-calls", type=int, default=1)
    args = parser.parse_args()
    campaign_path = args.campaign.resolve()
    campaign = json.loads(campaign_path.read_text(encoding="utf-8-sig"))
    if campaign["status"] not in ("approved", "running") or not campaign["approval"].get("approved_by"):
        raise SystemExit("campaign requires exact human approval")
    if args.max_calls < 1 or args.max_calls > campaign["loop"]["max_calls_per_invocation"]:
        raise SystemExit("invalid invocation call ceiling")
    if datetime.now(timezone.utc) >= datetime.fromisoformat(campaign["provider_snapshot"]["expires_at"]):
        raise SystemExit("provider snapshot expired")
    if (REPO / campaign["loop"]["kill_switch"]).exists():
        raise SystemExit("kill switch active")
    lock_path = campaign_path.with_suffix(".runner.lock")
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise SystemExit("campaign runner lock exists")
    executed = 0
    try:
        campaign["status"] = "running"
        save(campaign_path, campaign)
        while executed < args.max_calls and campaign["provider_calls"] < campaign["loop"]["max_total_provider_calls"]:
            if (REPO / campaign["loop"]["kill_switch"]).exists():
                campaign["status"] = "stopped-by-kill-switch"
                break
            full = next((row for row in campaign["runs"] if row["arm"] == "full" and row["status"] in ("provider-complete","verified")), None)
            verifier = campaign["independent_verifier_runs"][0] if campaign["independent_verifier_runs"] else None
            if full and verifier and verifier["status"] == "pending":
                full_run = REPO / "Evals/runs" / full["run_id"]
                run = prepare_verifier(campaign, full_run, verifier)
                save(campaign_path, campaign)
                code = invoke_provider(run.name, campaign)
                campaign["provider_calls"] += 1; executed += 1
                verifier["status"] = "provider-complete" if code == 0 else "provider-failed"
                if code != 0:
                    campaign["status"] = "stopped-after-provider-failure"; break
                finalize = call([sys.executable, str(HERE / "finalize_full_verification.py"), "--solution-run", str(full_run), "--verifier-run", str(run)], 120)
                grade = call([sys.executable, str(HERE / "grade_adaptive_run.py"), "--run", str(full_run), "--repo", str(REPO)], 180)
                verifier["status"] = "complete" if finalize == 0 else "complete-quality-failure"
                full["status"] = "graded" if grade == 0 else "grading-failed"
                if grade != 0:
                    campaign["status"] = "stopped-after-invalid-grader-outcome"; break
            else:
                entry = next((row for row in campaign["runs"] if row["status"] == "pending"), None)
                if not entry:
                    break
                run = prepare_solution(campaign, entry)
                save(campaign_path, campaign)
                code = invoke_provider(run.name, campaign)
                campaign["provider_calls"] += 1; executed += 1
                entry["status"] = "provider-complete" if code == 0 else "provider-failed"
                if code != 0:
                    campaign["status"] = "stopped-after-provider-failure"; break
                if entry["arm"] != "full":
                    grade = call([sys.executable, str(HERE / "grade_adaptive_run.py"), "--run", str(run), "--repo", str(REPO)], 180)
                    entry["status"] = "graded" if grade == 0 else "grading-failed"
                    if grade != 0:
                        campaign["status"] = "stopped-after-grading-failure"; break
            save(campaign_path, campaign)
        all_solutions = all(row["status"] == "graded" for row in campaign["runs"])
        verifier_done = (not campaign["independent_verifier_runs"]
                         or campaign["independent_verifier_runs"][0]["status"] in ("complete", "complete-quality-failure"))
        if all_solutions and verifier_done and campaign["provider_calls"] == campaign["loop"]["max_total_provider_calls"]:
            campaign["status"] = "complete"
        save(campaign_path, campaign)
        print(json.dumps({"campaign_id":campaign["campaign_id"],"executed_this_invocation":executed,"provider_calls_total":campaign["provider_calls"],"status":campaign["status"]},indent=2))
    finally:
        os.close(fd)
        lock_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
