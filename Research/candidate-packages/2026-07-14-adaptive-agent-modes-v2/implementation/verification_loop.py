#!/usr/bin/env python3
"""The verification loop: run harness checks, hand failures back, iterate to green.

Implements F-2026-07-12-009 ("engineer the loop, not the prompt") as a
mechanism instead of an instruction: every iteration runs the INDEPENDENT
check suite (harness_checks.py) and returns structured failures to the agent
via .agentic/loop-feedback.json. Termination is hard, never vibes:

  green             every check passes -> the loop's goal is met
  iteration-budget  max_iterations reached -> stop, escalate to the owner
  no-progress       the failure fingerprint is identical no_progress_limit
                    times in a row -> stop (the agent is looping, not fixing)

The loop state and budgets live inside the frozen suite config, so an agent
cannot buy itself iterations or disable no-progress termination.

Exit codes: 0 green | 1 failures remain, iterate | 2 terminated (budget or
no-progress) | 3 integrity failure (suite tampered or unreadable).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import harness_checks

DEFAULT_MAX_ITERATIONS = 5
DEFAULT_NO_PROGRESS_LIMIT = 2


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def dump(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def budgets(suite: dict[str, Any]) -> tuple[int, int]:
    config = suite.get("config", {})
    return (int(config.get("max_iterations", DEFAULT_MAX_ITERATIONS)),
            int(config.get("no_progress_limit", DEFAULT_NO_PROGRESS_LIMIT)))


def evaluate_state(state: dict[str, Any], suite: dict[str, Any]) -> str:
    """Return the loop verdict for the recorded iterations."""
    iterations = state.get("iterations", [])
    if iterations and iterations[-1]["green"]:
        return "green"
    max_iterations, no_progress_limit = budgets(suite)
    if len(iterations) >= max_iterations:
        return "iteration-budget"
    fingerprints = [row["failure_fingerprint"] for row in iterations if not row["green"]]
    if len(fingerprints) >= no_progress_limit and len(set(fingerprints[-no_progress_limit:])) == 1:
        return "no-progress"
    return "continue"


def step(suite_path: Path, workspace: Path) -> dict[str, Any]:
    suite = load(suite_path)
    integrity = harness_checks.verify_suite_integrity(suite)
    if integrity:
        return {"verdict": "integrity-failure", "integrity_failures": integrity}
    agentic = workspace / ".agentic"
    state_path = agentic / "loop-state.json"
    state = load(state_path) if state_path.is_file() else {"schema_version": 1, "iterations": []}

    report = harness_checks.run_suite(suite, workspace)
    state["iterations"].append({
        "iteration": len(state["iterations"]) + 1,
        "green": report["green"],
        "failing_check_ids": report["failing_check_ids"],
        "failure_fingerprint": report["failure_fingerprint"],
    })
    verdict = evaluate_state(state, suite)
    state["verdict"] = verdict
    dump(state_path, state)
    dump(agentic / "loop-report.json", report)

    feedback = {
        "schema_version": 1,
        "verdict": verdict,
        "iteration": len(state["iterations"]),
        "max_iterations": budgets(suite)[0],
        "instruction": {
            "green": "All independent checks pass. Proceed to the pre-submit gate.",
            "continue": "Fix the failures below, then run the loop step again. Do not weaken or remove checks; the suite is frozen.",
            "iteration-budget": "Iteration budget exhausted. Stop and escalate to the owner with the remaining failures.",
            "no-progress": "No progress across consecutive iterations. Stop, diagnose the approach itself, and escalate to the owner.",
        }[verdict],
        "failures": [
            {"check_id": row["id"], "kind": row["kind"], "failures": row["failures"],
             **({"guidance": row["guidance"]} if row.get("guidance") else {})}
            for row in report["checks"] if row["verdict"] != "PASS"
        ],
    }
    dump(agentic / "loop-feedback.json", feedback)
    return {"verdict": verdict, "iteration": len(state["iterations"]), "report": report, "feedback": feedback}


def ingest_findings(suite_path: Path, findings_path: Path) -> dict[str, Any]:
    """Append independent-verifier findings to the suite as blocking checks.

    Findings are harness-side additions (the verifier is part of the harness,
    not the agent), so the freeze digest is recomputed to cover them. Each
    finding stays failing until finding-resolutions.json names a proving
    command that re-executes green, or an explicit owner waiver.
    """
    suite = load(suite_path)
    integrity = harness_checks.verify_suite_integrity(suite)
    if integrity:
        return {"verdict": "integrity-failure", "integrity_failures": integrity}
    findings = load(findings_path)
    existing = {str(row.get("id")) for row in suite.get("checks", [])}
    added = []
    for row in findings.get("findings", []):
        finding_id = f"finding:{row.get('id')}"
        if finding_id in existing:
            continue
        suite["checks"].append({
            "id": finding_id,
            "kind": "finding",
            "authored_by": "harness",
            "severity": row.get("severity", "blocking"),
            "claim": row.get("claim", ""),
        })
        added.append(finding_id)
    suite["harness_freeze_sha256"] = harness_checks.harness_freeze_sha256(suite)
    dump(suite_path, suite)
    return {"verdict": "ingested", "added": added, "total_checks": len(suite["checks"])}


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    run = sub.add_parser("step", help="run one loop iteration")
    run.add_argument("--suite", type=Path, required=True)
    run.add_argument("--workspace", type=Path, required=True)
    ingest = sub.add_parser("ingest-findings", help="add verifier findings to the suite as blocking checks")
    ingest.add_argument("--suite", type=Path, required=True)
    ingest.add_argument("--findings", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "ingest-findings":
        result = ingest_findings(args.suite, args.findings)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(0 if result["verdict"] == "ingested" else 3)
    result = step(args.suite, args.workspace.resolve())
    print(json.dumps({key: result[key] for key in ("verdict", "iteration") if key in result}
                     | {"failing": result.get("report", {}).get("failing_check_ids", [])}
                     | ({"integrity_failures": result["integrity_failures"]} if "integrity_failures" in result else {}),
                     ensure_ascii=False, indent=2))
    raise SystemExit({"green": 0, "continue": 1, "iteration-budget": 2, "no-progress": 2, "integrity-failure": 3}[result["verdict"]])


if __name__ == "__main__":
    main()
