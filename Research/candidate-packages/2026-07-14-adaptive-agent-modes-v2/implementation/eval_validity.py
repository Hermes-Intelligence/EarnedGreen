#!/usr/bin/env python3
"""Audit public-contract/grader alignment and candidate fixture validity before spend."""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from fixture_admission import interpretation_coverage

HERE = Path(__file__).resolve().parent
CANDIDATE = HERE.parent
REPO = HERE.parents[3]


def resolve(relative: str) -> Path:
    return (CANDIDATE / relative) if relative.startswith("implementation/") else (REPO / relative)


def grader_ids(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8-sig")
    # Match only the grader's ``record("check-id", ...)`` calls at statement start and
    # constrain the id to an identifier-like token (kebab/snake), so prose or data
    # literals containing "record(" cannot be mistaken for declared check ids.
    return re.findall(r"(?m)^\s*record\(\s*[\"']([a-z0-9][a-z0-9._-]*)[\"']", text)


def run_json(command: list[str], cwd: Path) -> tuple[int, dict[str, Any] | None, str]:
    try:
        completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True,
                                   encoding="utf-8", errors="replace", timeout=30)
    except subprocess.TimeoutExpired as exc:
        partial = ((exc.stdout or "") + "\n" + (exc.stderr or "")).strip() if isinstance(exc.stdout, str) else ""
        message = f"timeout after 30s: {' '.join(str(part) for part in command)}\n{partial}"
        return 124, None, message[-2000:]
    output = (completed.stdout + "\n" + completed.stderr).strip()
    parsed = None
    for line in reversed(output.splitlines()):
        try:
            parsed = json.loads(line)
            break
        except json.JSONDecodeError:
            pass
    return completed.returncode, parsed, output[-2000:]


def merge_tree(source: Path, target: Path) -> None:
    shutil.copytree(source, target, dirs_exist_ok=True)


def static_issues(task: Path, grader: Path, candidate: bool) -> list[dict[str, str]]:
    task_text = task.read_text(encoding="utf-8-sig").lower()
    grader_text = grader.read_text(encoding="utf-8-sig").lower()
    issues = []
    if '"   "' in grader_text and "non-empty string" in task_text and not any(term in task_text for term in ("non-blank", "whitespace-only", "whitespace trimming")):
        issues.append({"category": "SPEC_AMBIGUITY", "detail": "grader rejects whitespace-only input but the task defines only non-empty"})
    if "legacy email is retained" in grader_text and "all(term in text" in grader_text and not any(term in task_text for term in ("verbatim", "exact phrase")):
        issues.append({"category": "GRADER_FAILURE", "detail": "semantic documentation is scored by a brittle literal substring"})
    if candidate and issues:
        issues.append({"category": "CANDIDATE_BLOCK", "detail": "candidate fixture remains misaligned"})
    return issues


def fixture_runtime(contract: dict[str, Any]) -> dict[str, Any]:
    fixture = contract["id"]
    public = REPO / f"Evals/fixtures/{fixture}/public"
    reference = REPO / f"Evals/fixtures/{fixture}/hidden/reference"
    grader = resolve(contract["candidate_grader"])
    catalog = json.loads((REPO / "Evals/fixtures/catalog.json").read_text(encoding="utf-8-sig"))
    fixture_def = next(row for row in catalog["fixtures"] if row["id"] == fixture)
    with tempfile.TemporaryDirectory(prefix="eval-validity-") as temp_name:
        temp = Path(temp_name)
        merge_tree(public, temp)
        merge_tree(reference, temp)
        public_cmd = [sys.executable, *fixture_def["public_test"][1:]]
        public_exit, _, public_out = run_json(public_cmd, temp)
        hidden_exit, hidden, hidden_out = run_json([sys.executable, str(grader), str(temp)], temp)
    controls = []
    for control in fixture_def.get("negative_controls", []):
        with tempfile.TemporaryDirectory(prefix="eval-control-") as temp_name:
            temp = Path(temp_name)
            merge_tree(public, temp)
            merge_tree(REPO / control["path"], temp)
            public_exit_control, _, _ = run_json([sys.executable, *fixture_def["public_test"][1:]], temp)
            hidden_exit_control, control_result, _ = run_json([sys.executable, str(grader), str(temp)], temp)
        controls.append({"id": control["id"], "public_pass": public_exit_control == 0, "hidden_rejected": hidden_exit_control != 0, "score": control_result.get("score") if control_result else None})
    variants = []
    for relative in contract.get("semantic_variant_paths", []):
        path = REPO / relative
        exit_code, result, output = run_json([sys.executable, str(grader), str(path)], path)
        variants.append({"path": relative, "passed": exit_code == 0 and result and result.get("score") == 100, "score": result.get("score") if result else None, "diagnostic": None if result else output})
    return {
        "reference_public_pass": public_exit == 0,
        "reference_hidden_pass": hidden_exit == 0 and hidden and hidden.get("score") == 100,
        "reference_score": hidden.get("score") if hidden else None,
        "negative_controls": controls,
        "semantic_variants": variants,
        "runtime_pass": public_exit == 0 and hidden_exit == 0 and hidden and hidden.get("score") == 100 and all(row["public_pass"] and row["hidden_rejected"] for row in controls) and all(row["passed"] for row in variants),
        "diagnostic": None if hidden else hidden_out or public_out,
    }


def validate() -> dict[str, Any]:
    contracts = json.loads((HERE / "eval-contracts.json").read_text(encoding="utf-8-sig"))
    results = []
    for contract in contracts["fixtures"]:
        historical_task = resolve(contract["historical_task"])
        historical_grader = resolve(contract["grader"])
        candidate_task = resolve(contract["candidate_task"])
        candidate_grader = resolve(contract["candidate_grader"])
        declared = contract["checks"]
        actual = grader_ids(historical_grader)
        task_normalized = re.sub(r"\s+", " ", candidate_task.read_text(encoding="utf-8-sig").lower())
        anchors = contract.get("public_anchors", {})
        anchor_failures = {
            check: expected
            for check, expected in anchors.items()
            if not any(re.sub(r"\s+", " ", phrase.lower()) in task_normalized for phrase in expected)
        }
        traceability = sorted(declared) == sorted(actual) and set(anchors) == set(declared) and not anchor_failures
        historical = static_issues(historical_task, historical_grader, False)
        candidate = static_issues(candidate_task, candidate_grader, True)
        # Interpretation coverage (open-world miss rule): when the public task
        # mentions registry/lookup/unknown/unseen/open-world concepts it must
        # state the miss/absent-case behavior explicitly. Contract-table
        # fixtures have no fixture-contract.json, so decision_points=None.
        coverage = interpretation_coverage(candidate_task.read_text(encoding="utf-8-sig"), None)
        runtime = fixture_runtime(contract)
        results.append({
            "id": contract["id"],
            "coverage_strategy": contract["coverage_strategy"],
            "traceability_pass": traceability,
            "missing_declared_checks": sorted(set(actual) - set(declared)),
            "stale_declared_checks": sorted(set(declared) - set(actual)),
            "missing_public_anchor_checks": sorted(set(declared) - set(anchors)),
            "unmatched_public_anchors": anchor_failures,
            "historical_validity": "FAIL" if historical else "PASS",
            "historical_issues": historical,
            "interpretation_coverage": coverage,
            "candidate_validity": "PASS" if not candidate and traceability and coverage["passed"] and runtime["runtime_pass"] else "FAIL",
            "candidate_issues": candidate,
            "runtime": runtime,
        })
    failed = [row for row in results if row["candidate_validity"] != "PASS"]
    return {
        "schema_version": 2,
        "verdict": "PASS" if not failed else "FAIL",
        "candidate_fixtures": len(results),
        "candidate_passed": len(results) - len(failed),
        "candidate_failed": len(failed),
        "historical_invalid": sum(row["historical_validity"] == "FAIL" for row in results),
        "provider_calls": 0,
        "results": results,
    }


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate()
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    raise SystemExit(0 if result["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
