#!/usr/bin/env python3
"""Admit a proposed check only if it demonstrably discriminates.

The verification loop is worth exactly the quality of its checks, and the known
failure mode of agent-authored checks is vacuity: `assert True`, or asserting
the behaviour that already exists. This gate settles that mechanically, with
zero model calls, by running each proposed check against the PRE-CHANGE
baseline snapshot the harness already takes:

  red-before-green-after  (a new-behaviour check)  MUST FAIL on the baseline
  green-before-green-after (a regression guard)    MUST PASS on the baseline

A check that passes before the feature exists proves nothing about the feature.

THE SUBTLETY THAT MAKES THIS REAL: the baseline failure must be an ASSERTION
failure, not an import/collection error. `import new_module` -> ImportError ->
red; the agent then creates an empty module -> green. That check is vacuous and
would sail through a naive gate. So a red caused by an error rather than an
assertion is `suspicious-red`: not admitted on its own, and routed to the
adversarial reviewer or back to the author.

Exit codes: 0 all proposed checks admitted | 1 at least one rejected.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import harness_checks

RED_BEFORE = "red-before-green-after"
GREEN_BEFORE = "green-before-green-after"
_EXPECTATIONS = {RED_BEFORE, GREEN_BEFORE}

# Markers that mean "this never got as far as asserting anything".
_ERROR_MARKERS = (
    "ModuleNotFoundError", "ImportError", "SyntaxError", "IndentationError",
    "NameError", "collection error", "ERRORS", "unable to import",
    "Traceback (most recent call last)",
)
_ASSERTION_MARKERS = ("AssertionError", "FAILED", "FAIL:", "assert ")


def classify_failure(output: str) -> str:
    """assertion | error | unknown - from a test runner's own vocabulary.

    An assertion marker wins over an error marker: pytest prints a traceback for
    a plain AssertionError too, so the presence of a traceback alone must not
    demote a genuine assertion failure.
    """
    if any(marker in output for marker in _ASSERTION_MARKERS):
        return "assertion"
    if any(marker in output for marker in _ERROR_MARKERS):
        return "error"
    return "unknown"


def _run_on(check: dict[str, Any], workspace: Path) -> tuple[bool, str]:
    """Run one check in a workspace. Returns (passed, combined_output)."""
    suite = {"schema_version": 1, "config": {}, "checks": [dict(check, authored_by="harness")]}
    suite["harness_freeze_sha256"] = harness_checks.harness_freeze_sha256(suite)
    report = harness_checks.run_suite(suite, workspace)
    row = report["checks"][0]
    output = " ".join(
        str(failure.get("output_tail", "")) + " " + str(failure.get("reason", ""))
        for failure in row["failures"]
    )
    return row["verdict"] == "PASS", output


def admit(proposed: list[dict[str, Any]], baseline_dir: Path) -> dict[str, Any]:
    """Classify every proposed check against the pre-change baseline."""
    baseline_dir = Path(baseline_dir)
    rows: list[dict[str, Any]] = []
    for check in proposed:
        expectation = check.get("expectation")
        verdict: str
        reason: str
        if expectation not in _EXPECTATIONS:
            rows.append({"id": check.get("id"), "verdict": "rejected",
                         "reason": f"check declares no valid expectation (got {expectation!r}; "
                                   f"expected one of {sorted(_EXPECTATIONS)})"})
            continue
        if not str(check.get("requirement_ref", "")).strip():
            rows.append({"id": check.get("id"), "verdict": "rejected",
                         "reason": "check names no requirement_ref: a check that maps to no requirement "
                                   "cannot be reviewed and cannot prove a requirement is met"})
            continue
        passed, output = _run_on(check, baseline_dir)
        failure_kind = None if passed else classify_failure(output)
        if expectation == RED_BEFORE:
            if passed:
                verdict, reason = "rejected", ("VACUOUS: the check passes on the pre-change code, so it cannot be "
                                               "evidence that the new behaviour was implemented")
            elif failure_kind == "assertion":
                verdict, reason = "admitted", "fails on the baseline with an assertion: it discriminates"
            else:
                verdict, reason = "suspicious-red", (
                    f"fails on the baseline but not via an assertion ({failure_kind}). An import/collection error goes "
                    "green as soon as the symbol merely exists, which would make this check vacuous. Restructure it so "
                    "the assertion is what fails, or send it to adversarial review.")
        else:  # GREEN_BEFORE
            if passed:
                verdict, reason = "admitted", "passes on the baseline: a valid regression guard"
            else:
                verdict, reason = "rejected", ("asserts something already broken on the pre-change code: it would be red "
                                               "for a reason the agent did not cause")
        rows.append({"id": check.get("id"), "expectation": expectation,
                     "requirement_ref": check.get("requirement_ref"),
                     "baseline_passed": passed, "baseline_failure_kind": failure_kind,
                     "verdict": verdict, "reason": reason})
    admitted = [row for row in rows if row["verdict"] == "admitted"]
    return {
        "schema_version": 1,
        "verdict": "PASS" if len(admitted) == len(rows) and rows else "FAIL",
        "proposed": len(rows),
        "admitted": len(admitted),
        "rejected": [row for row in rows if row["verdict"] == "rejected"],
        "suspicious": [row for row in rows if row["verdict"] == "suspicious-red"],
        "checks": rows,
        "rule": ("a check is admitted only if it demonstrably discriminates on the pre-change code; "
                 "vacuous and error-red checks never become evidence"),
    }


def requirement_coverage(admitted: list[dict[str, Any]], ledger: dict[str, Any]) -> dict[str, Any]:
    """Which compiled requirements have at least one admitted check?

    This is where the requirement ledger stops being prose the agent reads and
    becomes the index of what must be provably true.
    """
    covered = {row.get("requirement_ref") for row in admitted}
    requirements = [row["id"] for row in ledger.get("requirements", [])]
    uncovered = [row for row in requirements if row not in covered]
    return {
        "requirements": len(requirements),
        "covered": len(requirements) - len(uncovered),
        "uncovered_requirement_ids": uncovered,
        "complete": not uncovered,
    }


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser()
    parser.add_argument("--proposed", type=Path, required=True, help="JSON with a `checks` array")
    parser.add_argument("--baseline", type=Path, required=True, help="pre-change baseline workspace")
    parser.add_argument("--ledger", type=Path, help="objective ledger, to report requirement coverage")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    proposed = json.loads(args.proposed.read_text(encoding="utf-8-sig")).get("checks", [])
    result = admit(proposed, args.baseline)
    if args.ledger:
        ledger = json.loads(args.ledger.read_text(encoding="utf-8-sig"))
        admitted = [row for row in result["checks"] if row["verdict"] == "admitted"]
        result["requirement_coverage"] = requirement_coverage(admitted, ledger)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    raise SystemExit(0 if result["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
