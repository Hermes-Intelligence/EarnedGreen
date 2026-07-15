import importlib.util
import json
import sys
import time
from pathlib import Path

module_path = Path(sys.argv[1]) / "src/parser.py"
spec = importlib.util.spec_from_file_location("src.parser", module_path)
module = importlib.util.module_from_spec(spec)
sys.path.insert(0, str(Path(sys.argv[1])))
spec.loader.exec_module(module)
checks = []


def record(identifier, weight, fn):
    try:
        passed = bool(fn())
    except Exception:
        passed = False
    checks.append({"id": identifier, "weight": weight, "passed": passed})


def rejects(value):
    try:
        module.parse_record(value)
        return False
    except ValueError:
        return True


def escaped_values():
    line = r"A\|B|key\=part=value\|tail|path=c:\\tmp"
    return module.parse_record(line) == {"kind": "A|B", "fields": {"key=part": "value|tail", "path": r"c:\tmp"}}


def malformed_isolation():
    result = module.parse_batch(["NEW|x=1", "broken", "NEXT|y=2"])
    return result["accepted"] == [{"kind": "NEW", "fields": {"x": "1"}}, {"kind": "NEXT", "fields": {"y": "2"}}] and result["rejected"] == [{"index": 1, "code": "invalid_record"}]


def performance():
    lines = [f"K{i % 17}|field_{i}=value_{i}" for i in range(5000)]
    started = time.perf_counter()
    result = module.parse_batch(lines)
    return len(result["accepted"]) == len(lines) and time.perf_counter() - started < 2.5


record("known-contract", 15, lambda: module.parse_record("USER|id=7") == {"kind": "USER", "fields": {"id": "7"}})
record("unseen-kind", 15, lambda: module.parse_record("TELEMETRY_V9|id=x")["kind"] == "TELEMETRY_V9")
record("unseen-fields", 15, lambda: module.parse_record("X|planet=mars|trace_id=9")["fields"] == {"planet": "mars", "trace_id": "9"})
record("escaped-components", 15, escaped_values)
record("unicode", 10, lambda: module.parse_record("事件|właściciel=Łódź|地域=東京")["fields"]["地域"] == "東京")
record("malformed-isolation", 10, malformed_isolation)
record("duplicate-and-invalid", 10, lambda: all(rejects(value) for value in ("", "K", "|a=1", "K|=1", "K|a=1|a=2", "K|a=x\\q", "K|a=x\\")))
record("linear-batch", 10, performance)

score = sum(item["weight"] for item in checks if item["passed"])
print(json.dumps({"passed": score == 100, "score": score, "checks": checks}))
sys.exit(0 if score == 100 else 1)
