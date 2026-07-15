#!/usr/bin/env python3
"""Validate the Mode 1/2/3 boundary fixture without provider calls."""
from __future__ import annotations

import argparse, json, re, shutil, subprocess, sys, tempfile
from pathlib import Path

HERE=Path(__file__).resolve().parent; FIXTURE=HERE/"mode-boundary-fixture"


def merge(source, target): shutil.copytree(source,target,dirs_exist_ok=True)
def execute(command,cwd):
    done=subprocess.run(command,cwd=cwd,text=True,capture_output=True,encoding="utf-8",errors="replace",timeout=30)
    parsed=None
    for line in reversed((done.stdout+"\n"+done.stderr).splitlines()):
        try: parsed=json.loads(line); break
        except json.JSONDecodeError: pass
    return done.returncode,parsed,(done.stdout+done.stderr)[-1500:]


def variant(overlay):
    contract=json.loads((FIXTURE/"fixture-contract.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="mode-boundary-") as name:
        workspace=Path(name); merge(FIXTURE/"public",workspace); merge(overlay,workspace)
        public_exit,_,public_diag=execute([sys.executable,"-m","unittest","discover","-s","tests","-p","test_public.py","-v"],workspace)
        hidden_exit,result,hidden_diag=execute([sys.executable,str(FIXTURE/contract["hidden_grader"]),str(workspace)],workspace)
    return {"public_pass":public_exit==0,"hidden_pass":hidden_exit==0,"score":result.get("score") if result else None,"diagnostic":None if result else hidden_diag or public_diag}


def main():
    try: sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError): pass
    parser=argparse.ArgumentParser(); parser.add_argument("--output",type=Path,required=True); args=parser.parse_args()
    contract=json.loads((FIXTURE/"fixture-contract.json").read_text(encoding="utf-8")); task=(FIXTURE/"public/task.md").read_text(encoding="utf-8")
    grader=(FIXTURE/contract["hidden_grader"]).read_text(encoding="utf-8")
    actual=re.findall(r'record\("([a-z0-9-]+)"',grader)
    traceability=sorted(actual)==sorted(contract["checks"]) and all(anchor.lower() in task.lower() for anchor in contract["public_anchors"].values())
    normalized=task.lower()
    registry_miss_policy_explicit=any(phrase in normalized for phrase in ("no handler", "absent from the registry", "not present in the registry", "pass through unchanged", "must not raise"))
    grader_check_isolation="fixture-runtime" not in grader
    overlays={
        "mode-1-local":FIXTURE/"negative-controls/mode-1-local",
        "reject-on-miss":FIXTURE/"negative-controls/reject-on-miss",
        "mode-2-routed":FIXTURE/"negative-controls/mode-2-routed",
        "reference-mode-3":FIXTURE/"hidden/reference",
    }
    results=[]
    for expected in contract["expected_controls"]:
        outcome=variant(overlays[expected["id"]]); score=outcome["score"]
        outcome.update({"id":expected["id"],"expected_range":[expected["min_score"],expected["max_score"]],"range_pass":score is not None and expected["min_score"]<=score<=expected["max_score"]})
        results.append(outcome)
    ordered=all(results[i]["score"] < results[i+1]["score"] for i in range(len(results)-1))
    valid=traceability and registry_miss_policy_explicit and grader_check_isolation and ordered and all(row["public_pass"] and row["range_pass"] for row in results) and results[-1]["hidden_pass"] and all(not row["hidden_pass"] for row in results[:-1])
    result={"schema_version":2,"verdict":"PASS" if valid else "FAIL","provider_calls":0,"traceability_pass":traceability,"registry_miss_policy_explicit":registry_miss_policy_explicit,"grader_check_isolation":grader_check_isolation,"ordered_separation_pass":ordered,"controls":results,"failures":(["public task does not define behavior when a valid type has no registry handler"] if not registry_miss_policy_explicit else [])+(["grader masks later dimensions after an early runtime exception"] if not grader_check_isolation else [])}
    args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2)); raise SystemExit(0 if valid else 1)


if __name__=="__main__": main()
