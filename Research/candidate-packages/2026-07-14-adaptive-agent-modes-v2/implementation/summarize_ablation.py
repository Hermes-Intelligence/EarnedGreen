#!/usr/bin/env python3
"""Summarize quality, gate compliance, time and tokens without auto-promoting policy."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path


RANK = {"vanilla":0,"mode-1-lean":1,"mode-2-routed":2,"mode-3-assured":3,"full":4}


def seconds(execution: dict) -> float | None:
    try:
        return (datetime.fromisoformat(execution["finished_at"]) - datetime.fromisoformat(execution["started_at"])).total_seconds()
    except Exception:
        return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    campaign = json.loads(args.campaign.read_text(encoding="utf-8-sig"))
    rows = []
    validity_issues = []
    for entry in campaign["runs"]:
        run = args.repo / "Evals/runs" / entry["run_id"]
        record = json.loads((run / "run-record.json").read_text(encoding="utf-8-sig"))
        execution = json.loads((run / "provider-execution.json").read_text(encoding="utf-8-sig"))
        tokens = record["token_usage"].get("total_observed_tokens", 0)
        wall = seconds(execution)
        verifier = None
        attribution = None
        if entry["arm"] == "full":
            verifier_entry = campaign["independent_verifier_runs"][0]
            verifier_run = args.repo / "Evals/runs" / verifier_entry["run_id"]
            verifier_execution = json.loads((verifier_run / "provider-execution.json").read_text(encoding="utf-8-sig"))
            tokens += verifier_execution.get("token_usage", {}).get("total_observed_tokens", 0)
            verifier_wall = seconds(verifier_execution)
            wall = (wall or 0) + (verifier_wall or 0)
            verifier = json.loads((run / "full-verification-result.json").read_text(encoding="utf-8-sig"))
            pre_submit = json.loads((run / "workspace/.agentic/pre-submit-result.json").read_text(encoding="utf-8-sig"))
            portability_failures = [row for row in pre_submit.get("failures", []) if "observed exit 9009" in row.get("reason", "") and "python3" in row.get("reason", "")]
            if verifier.get("verifier_valid") and portability_failures and len(portability_failures) == len(pre_submit.get("failures", [])):
                attribution = "HARNESS_PLATFORM_MISMATCH"
                validity_issues.append({"arm":"full","category":attribution,"reason":"host final gate treated the Linux python3 launcher as product failure despite verifier PASS"})
        if entry["arm"] == "vanilla":
            manifest = json.loads((run / "run-manifest.json").read_text(encoding="utf-8-sig"))
            prompt = (run / "prompt.txt").read_text(encoding="utf-8-sig")
            if manifest.get("agent_context_files") or "Read-only/trivial mode selected. Do not mutate files." in prompt:
                attribution = "INVALID_CONTROL_PROMPT"
                validity_issues.append({"arm":"vanilla","category":attribution,"reason":"the supposed coding baseline received Candidate read-only scaffolding and was prohibited from editing"})
        gate_ok = bool(record["enforcement_passed"])
        critical_failure = not record["public_tests"]["passed"] or not gate_ok or (entry["arm"] == "full" and not verifier.get("verifier_valid"))
        rows.append({"arm":entry["arm"],"rank":RANK[entry["arm"]],"product_score":record["grader"]["score"],"public_pass":record["public_tests"]["passed"],"completion_gate_pass":gate_ok,"critical_failure":critical_failure,"failure_attribution":attribution,"wall_seconds":wall,"observed_tokens":tokens,"actual_model":record["actual_model"],"effort":record["effort"],"quality_passed":record["quality_passed"]})
    rows.sort(key=lambda row: row["rank"])
    best = max(row["product_score"] for row in rows)
    eligible = [row for row in rows if row["product_score"] >= best - 3 and not row["critical_failure"]]
    raw_recommendation = min(eligible, key=lambda row: row["rank"])["arm"] if eligible else None
    comparative_valid = not validity_issues
    recommendation = raw_recommendation if comparative_valid else None
    result = {"schema_version":2,"campaign_id":campaign["campaign_id"],"status":"candidate-screen-only" if comparative_valid else "candidate-screen-invalid","provider_calls":campaign["provider_calls"],"comparative_valid":comparative_valid,"validity_issues":validity_issues,"arms":rows,"best_product_score":best,"raw_rule_recommendation":raw_recommendation,"candidate_recommendation":recommendation,"decision_rule":"lowest mode within 3 points of best with no critical failure, only when control and completion-gate validity pass","stable_policy_changed":False,"next_action":"repair and zero-provider-test the invalid control and platform boundary; any replacement screen requires separate approval" if not comparative_valid else "replicate only a signaled boundary on a second task family under separate approval"}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
