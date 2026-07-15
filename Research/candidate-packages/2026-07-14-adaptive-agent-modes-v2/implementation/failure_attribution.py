#!/usr/bin/env python3
"""Classify benchmark failures without blaming agents for invalid oracles."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


CATEGORIES = ["AGENT_FAILURE", "ROUTER_FAILURE", "ENFORCEMENT_FAILURE", "SPEC_AMBIGUITY", "GRADER_FAILURE", "INFRASTRUCTURE_FAILURE"]


def attribute(data: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for run in data["runs"]:
        fixture_issues = data.get("fixture_issues", {}).get(run["fixture"], {})
        for check in run.get("failed_checks", []):
            if check in fixture_issues.get("spec_ambiguity_checks", []):
                category = "SPEC_AMBIGUITY"
                confidence = "high"
                actionable = "clarify the public contract and version the fixture before another provider call"
            elif check in fixture_issues.get("grader_failure_checks", []):
                category = "GRADER_FAILURE"
                confidence = "high"
                actionable = "replace implementation-shaped or literal scoring with a semantic/behavioral oracle"
            elif run.get("infrastructure_failure"):
                category = "INFRASTRUCTURE_FAILURE"
                confidence = "high"
                actionable = "invalidate the run and repair infrastructure before replacement approval"
            elif run.get("pre_submit_gate") == "missing-or-soft":
                category = "ENFORCEMENT_FAILURE"
                confidence = "medium"
                actionable = "require a fail-closed objective/evidence gate before completion"
            elif run.get("router_relevance") == "failed":
                category = "ROUTER_FAILURE"
                confidence = "medium"
                actionable = "repair contextual routing and rerun a component ablation"
            else:
                category = "AGENT_FAILURE"
                confidence = "medium"
                actionable = "turn the missed behavior into a regression and evaluate the responsible mode component"
            rows.append({"run_id": run["run_id"], "fixture": run["fixture"], "arm": run["arm"], "failed_check": check, "category": category, "confidence": confidence, "action": actionable})
    invalid_quality = any(row["category"] in ("SPEC_AMBIGUITY", "GRADER_FAILURE", "INFRASTRUCTURE_FAILURE") for row in rows)
    systemic = []
    for issue in data.get("systemic_issues", []):
        if issue["category"] not in CATEGORIES:
            raise ValueError(f"unknown attribution category: {issue['category']}")
        systemic.append(issue)
    return {
        "schema_version": 2,
        "campaign_id": data["campaign_id"],
        "historical_result_immutable": True,
        "execution_integrity": data.get("execution_integrity", "UNKNOWN"),
        "quality_interpretation": "UNINTERPRETABLE_FOR_AFFECTED_CHECKS" if invalid_quality else "INTERPRETABLE",
        "valid_unaffected_pairs": data.get("valid_unaffected_pairs", []),
        "attributions": rows,
        "systemic_issues": systemic,
        "next_gate": "ZERO_PROVIDER_REPAIR_AND_ABLATION_DESIGN",
        "additional_provider_calls": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = attribute(json.loads(args.input.read_text(encoding="utf-8-sig")))
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
