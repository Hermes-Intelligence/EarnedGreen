#!/usr/bin/env python3
"""Resume a campaign after zero-provider regrading proves an infrastructure-only grader failure."""
from __future__ import annotations

import argparse, json
from datetime import datetime, timezone
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--campaign",type=Path,required=True); parser.add_argument("--runs-root",type=Path,required=True); args=parser.parse_args()
    data=json.loads(args.campaign.read_text(encoding="utf-8-sig"))
    if data.get("status") != "stopped-after-grading-failure": raise SystemExit("campaign is not stopped after grading failure")
    failed=[row for row in data["runs"] if row.get("status")=="grading-failed"]
    if len(failed)!=1: raise SystemExit("expected exactly one grading-failed run")
    row=failed[0]; run=args.runs_root/row["run_id"]
    execution=json.loads((run/"provider-execution.json").read_text(encoding="utf-8-sig")); record=json.loads((run/"run-record.json").read_text(encoding="utf-8-sig"))
    if execution.get("exit_code")!=0 or not execution.get("copied_back"): raise SystemExit("provider execution was not valid")
    if not record.get("outcome_valid"): raise SystemExit("regraded outcome is still invalid")
    row["status"]="graded"
    data["status"]="approved"
    data.setdefault("recoveries",[]).append({"at":datetime.now(timezone.utc).isoformat(),"run_id":row["run_id"],"kind":"zero-provider-host-grader-encoding-repair","provider_calls_added":0,"score":record["grader"]["score"]})
    args.campaign.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"campaign_id":data["campaign_id"],"status":data["status"],"recovered_run":row["run_id"],"score":record["grader"]["score"],"provider_calls":data["provider_calls"]},indent=2))


if __name__=="__main__": main()
