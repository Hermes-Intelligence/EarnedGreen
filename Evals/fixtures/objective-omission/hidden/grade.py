import copy
import importlib.util
import json
import sys
from pathlib import Path


def load(workspace):
    path = Path(workspace) / "src" / "policy.py"
    spec = importlib.util.spec_from_file_location("candidate_policy", path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module.build_policy


def rejected(fn, request):
    try: fn(request); return False
    except (ValueError, TypeError): return True


def main():
    checks=[]; error=None
    try:
        build=load(Path(sys.argv[1]).resolve())
        base={"name":" Łódź job ","targets":[{"type":" Queue ","value":" Główna "},{"type":"queue","value":"główna"},{"type":"future-kind","value":"東京"}],"extra":"discard"}
        original=copy.deepcopy(base); result=build(base)
        checks.append(("POL-001",base==original and result is not base and result["targets"] is not base["targets"]))
        checks.append(("POL-002",result["name"]=="Łódź job" and rejected(build,{"name":" ","targets":[{"type":"x","value":"y"}]})))
        checks.append(("POL-003",rejected(build,{"name":"x","targets":[]}) and rejected(build,{"name":"x","targets":[{"type":"","value":"y"}]})))
        checks.append(("POL-004",result["targets"][-1]=={"type":"future-kind","value":"東京"}))
        checks.append(("POL-005",result["targets"]==[{"type":"queue","value":"Główna"},{"type":"future-kind","value":"東京"}]))
        checks.append(("POL-006",result["timeout_seconds"]==30 and rejected(build,{"name":"x","targets":[{"type":"a","value":"b"}],"timeout_seconds":301})))
        checks.append(("POL-007",result["retries"]==2 and rejected(build,{"name":"x","targets":[{"type":"a","value":"b"}],"retries":6})))
        checks.append(("POL-008",result["dry_run"] is True and rejected(build,{"name":"x","targets":[{"type":"a","value":"b"}],"dry_run":"yes"})))
        checks.append(("POL-009",list(result)==["name","targets","timeout_seconds","retries","dry_run","metadata"] and "extra" not in result))
        secure={"name":"x","targets":[{"type":"a","value":"b"}],"metadata":{"Owner":"Ada","TOKEN":"x","nested":{"password":"p","keep":1},"items":[{"Api_Key":"k","ok":2}]}}
        secured=build(secure)
        checks.append(("POL-010",secured["metadata"].get("Owner")=="Ada" and rejected(build,{"name":"x","targets":[{"type":"a","value":"b"}],"metadata":[]})))
        text=json.dumps(secured["metadata"]).lower(); checks.append(("POL-011",all(k not in text for k in ['token','password','api_key','secret'])))
        checks.append(("POL-012",secured["metadata"].get("nested")=={"keep":1} and secured["metadata"].get("items")==[{"ok":2}]))
    except Exception as exc: error=repr(exc); checks.append(("grader-execution",False))
    passed=sum(1 for _,ok in checks if ok);total=len(checks)
    print(json.dumps({"schema_version":1,"case_id":"objective-omission","passed":passed==total,"score":round(100*passed/total,2),"checks":[{"id":i,"passed":ok} for i,ok in checks],"error":error},ensure_ascii=False))
    raise SystemExit(0 if passed==total else 1)


if __name__ == "__main__": main()
