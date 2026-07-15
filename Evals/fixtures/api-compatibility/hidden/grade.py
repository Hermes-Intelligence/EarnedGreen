import copy, importlib.util, json, sys
from pathlib import Path

p = Path(sys.argv[1]) / "src/client.py"
spec = importlib.util.spec_from_file_location("client", p)
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
checks = []
def check(i, v): checks.append((i, bool(v)))
def rejects(value):
    try: m.parse_user(value); return False
    except ValueError: return True
    except Exception: return False
try:
    legacy = {"id": "legacy-99", "name": "Zoë", "ignored": True}; before = copy.deepcopy(legacy)
    current = {"data": {"id": "future-314", "display_name": "Łukasz", "role": "owner"}}; current_before = copy.deepcopy(current)
    check("legacy", m.parse_user(legacy) == {"id": "legacy-99", "name": "Zoë"})
    check("current", m.parse_user(current) == {"id": "future-314", "name": "Łukasz"})
    check("no-mutation", legacy == before and current == current_before)
    invalid = [None, {}, {"id": "", "name": "A"}, {"id": 4, "name": "A"}, {"data": {"id": "x", "display_name": " "}}]
    check("validation", all(rejects(x) for x in invalid))
except Exception: check("execution", False)
n = sum(v for _, v in checks)
print(json.dumps({"passed": n == len(checks), "score": 100*n/len(checks), "checks": [{"id": i, "passed": v} for i,v in checks]}))
sys.exit(0 if n == len(checks) else 1)
