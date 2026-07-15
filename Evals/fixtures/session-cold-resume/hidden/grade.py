import importlib.util, json, sys, tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

p = Path(sys.argv[1]) / "src/checkpoint.py"
spec = importlib.util.spec_from_file_location("checkpoint", p)
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
checks = []
def check(i, v): checks.append((i, bool(v)))
def rejects(fn):
    try: fn(); return False
    except ValueError: return True
    except Exception: return False
try:
    now = datetime(2030, 1, 8, tzinfo=timezone.utc)
    base = {"schema_version":1,"objective_id":"OBJ-9","task":"resume","status":"in_progress","updated_at":now.isoformat(),"decisions":[{"id":"D1","api_token":"hide"}],"evidence":[],"blockers":[],"next_action":"validate integration","changed_paths":[],"Password":"hide-too"}
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "state.json"; m.save_checkpoint(path, base)
        raw = path.read_text(encoding="utf-8"); loaded = m.load_checkpoint(path, now=now)
        check("secrets-redacted", "hide" not in raw and "Password" not in raw and "api_token" not in raw)
        check("roundtrip", loaded["objective_id"] == "OBJ-9" and loaded["next_action"] == "validate integration")
        bad = dict(base); bad["next_action"] = ""
        check("invalid-rejected", rejects(lambda: m.save_checkpoint(path, bad)))
        stale = dict(base); stale["updated_at"] = (now - timedelta(hours=169)).isoformat(); m.save_checkpoint(path, stale)
        check("stale-rejected", rejects(lambda: m.load_checkpoint(path, max_age_hours=168, now=now)))
        path.write_text("{bad", encoding="utf-8")
        check("malformed-rejected", rejects(lambda: m.load_checkpoint(path, now=now)))
except Exception: check("execution", False)
n = sum(v for _, v in checks)
print(json.dumps({"passed": n == len(checks), "score": 100*n/len(checks), "checks": [{"id": i, "passed": v} for i,v in checks]}))
sys.exit(0 if n == len(checks) else 1)
