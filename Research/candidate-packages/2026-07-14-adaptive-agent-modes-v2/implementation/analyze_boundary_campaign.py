#!/usr/bin/env python3
"""Attribute the completed boundary campaign without rewriting historical runs."""
from __future__ import annotations

import argparse, json
from datetime import datetime
from pathlib import Path


def elapsed(execution):
    return round((datetime.fromisoformat(execution["finished_at"])-datetime.fromisoformat(execution["started_at"])).total_seconds(),1)


def main():
    p=argparse.ArgumentParser(); p.add_argument("--campaign",type=Path,required=True); p.add_argument("--repo",type=Path,required=True); p.add_argument("--output",type=Path,required=True); a=p.parse_args()
    campaign=json.loads(a.campaign.read_text(encoding="utf-8-sig")); rows=[]; run_ids=[]
    for entry in campaign["runs"]:
        run=a.repo/"Evals/runs"/entry["run_id"]; record=json.loads((run/"run-record.json").read_text(encoding="utf-8-sig")); execution=json.loads((run/"provider-execution.json").read_text(encoding="utf-8-sig")); run_ids.append(entry["run_id"])
        failures=[row for row in record["grader"].get("checks",[]) if not row.get("passed")]
        rows.append({"arm":entry["arm"],"run_id":entry["run_id"],"score":record["grader"]["score"],"public_pass":record["public_tests"]["passed"],"outcome_valid":record["outcome_valid"],"completion_gate_pass":record["enforcement_passed"],"observed_tokens":record["tokens"],"wall_seconds":elapsed(execution),"failed_checks":[row["id"] for row in failures],"failure_details":[row.get("detail","") for row in failures]})
    verifier=campaign["independent_verifier_runs"][0]; run_ids.append(verifier["run_id"]); vrun=a.repo/"Evals/runs"/verifier["run_id"]; vex=json.loads((vrun/"provider-execution.json").read_text(encoding="utf-8-sig"))
    full=next(row for row in campaign["runs"] if row["arm"]=="full"); full_result=json.loads((a.repo/"Evals/runs"/full["run_id"]/"full-verification-result.json").read_text(encoding="utf-8-sig")); task=(a.repo/"Research/candidate-packages/2026-07-14-adaptive-agent-modes-v2/implementation/mode-boundary-fixture/public/task.md").read_text(encoding="utf-8-sig").lower()
    unknown_policy_explicit=any(phrase in task for phrase in ("no handler", "absent from the registry", "not present in the registry", "pass through unchanged", "must not raise"))
    shared_unknown_failure=all(any("unknown entity type" in detail.lower() for detail in row["failure_details"]) for row in rows)
    masked=all(row["failed_checks"]==["fixture-runtime"] for row in rows)
    issues=[]
    if shared_unknown_failure and not unknown_policy_explicit: issues.append({"category":"SPEC_AMBIGUITY","reason":"all five independent solutions and the Full verifier treated an unregistered-but-valid type as a counted rejection, while the hidden reference silently required pass-through; the public task never states registry-miss behavior"})
    if masked: issues.append({"category":"GRADER_FAILURE","reason":"one early exception collapses the remaining eight hidden checks into fixture-runtime, so the 9/100 scores do not measure the other dimensions"})
    if full_result.get("verifier_valid") and not full_result.get("final_gate_passed"): issues.append({"category":"HARNESS_PLATFORM_MISMATCH","reason":"the independent verifier returned PASS, but the Windows final gate re-executed visible python3 aliases and received exit 9009"})
    integrity=campaign.get("provider_calls")==6 and len(run_ids)==len(set(run_ids))==6 and all(row["outcome_valid"] for row in rows)
    result={"schema_version":1,"campaign_id":campaign["campaign_id"],"execution_integrity":"PASS" if integrity else "FAIL","provider_calls":campaign["provider_calls"],"unique_run_ids":len(set(run_ids)),"comparative_verdict":"INVALID","candidate_recommendation":None,"arms":sorted(rows,key=lambda r:{"vanilla":0,"mode-1-lean":1,"mode-2-routed":2,"mode-3-assured":3,"full":4}[r["arm"]]),"full_verifier":{"status":verifier["status"],"verifier_valid":full_result.get("verifier_valid"),"observed_tokens":vex["token_usage"]["total_observed_tokens"],"wall_seconds":elapsed(vex)},"validity_issues":issues,"stable_policy_changed":False,"provider_calls_authorized_after_campaign":0,"next_action":"version the fixture: specify registry-miss semantics, isolate every hidden check, add a reasonable reject-on-miss semantic control, strengthen ambiguity/open-world gates, and locally validate before any separately approved provider campaign"}
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); print(json.dumps(result,ensure_ascii=False,indent=2)); raise SystemExit(0 if integrity and issues else 1)


if __name__=="__main__": main()
