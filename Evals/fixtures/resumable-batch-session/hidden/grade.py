import copy
import hashlib
import importlib
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(sys.argv[1])))
worker = importlib.import_module("src.worker")
checks = []


def record(identifier, weight, fn):
    try:
        passed = bool(fn())
    except Exception:
        passed = False
    checks.append({"id": identifier, "weight": weight, "passed": passed})


def with_path(fn):
    with tempfile.TemporaryDirectory() as directory:
        return fn(Path(directory) / "checkpoint.json")


def one_shot():
    return with_path(lambda path: worker.run_batch([1, 2], path, lambda item, key: item * 2) == {"processed": [{"index": 0, "result": 2}, {"index": 1, "result": 4}], "completed": 2, "done": True})


def split_resume():
    def run(path):
        calls = []
        process = lambda item, key: calls.append((item, key)) or item
        first = worker.run_batch(["a", "b", "c"], path, process, max_items=2)
        second = worker.run_batch(["a", "b", "c"], path, process)
        return first["completed"] == 2 and not first["done"] and second == {"processed": [{"index": 2, "result": "c"}], "completed": 3, "done": True} and [item for item, _ in calls] == ["a", "b", "c"]
    return with_path(run)


def stable_keys():
    def run(path):
        keys = []
        items = [{"x": 1}, {"x": 2}]
        worker.run_batch(items, path, lambda item, key: keys.append(key))
        # task.md does not pin the exact canonical-JSON kwargs, so derive the
        # expected keys from the candidate's OWN persisted input_digest rather
        # than re-deriving with one fixed serialization. Any self-consistent
        # canonicalization (the key formula is sha256(f"{input_digest}:{i}"))
        # therefore passes, while an inconsistent or non-deterministic scheme
        # still fails.
        state = json.loads(Path(path).read_text(encoding="utf-8"))
        digest = state["input_digest"]
        expected = [hashlib.sha256(f"{digest}:{index}".encode("utf-8")).hexdigest() for index in range(2)]
        return keys == expected and len(set(keys)) == 2
    return with_path(run)


def failure_resume():
    def run(path):
        calls = []
        def fail(item, key):
            calls.append(item)
            if item == 2:
                raise RuntimeError("stop")
            return item
        try:
            worker.run_batch([1, 2, 3], path, fail)
        except RuntimeError:
            pass
        else:
            return False
        resumed = []
        result = worker.run_batch([1, 2, 3], path, lambda item, key: resumed.append(item) or item)
        return calls == [1, 2] and resumed == [2, 3] and result["completed"] == 3
    return with_path(run)


def mismatch_rejected():
    def run(path):
        worker.run_batch([1], path, lambda item, key: item)
        called = []
        try:
            worker.run_batch([2], path, lambda item, key: called.append(item))
            return False
        except ValueError:
            return called == []
    return with_path(run)


def corrupt_rejected():
    def run(path):
        path.write_text("not-json", encoding="utf-8")
        called = []
        try:
            worker.run_batch([1], path, lambda item, key: called.append(item))
            return False
        except ValueError:
            return called == []
    return with_path(run)


def safe_schema():
    def run(path):
        secret = {"id": 1, "api_token": "do-not-store"}
        worker.run_batch([secret], path, lambda item, key: {"authorization": "also-secret"})
        data = json.loads(path.read_text(encoding="utf-8"))
        return set(data) == {"version", "input_digest", "completed_indices"} and data["completed_indices"] == [0] and "secret" not in path.read_text(encoding="utf-8") and "token" not in path.read_text(encoding="utf-8")
    return with_path(run)


def atomic_cleanup():
    def run(path):
        worker.run_batch([1, 2], path, lambda item, key: item)
        return path.exists() and not list(path.parent.glob("*.tmp"))
    return with_path(run)


def validation():
    return with_path(lambda path: _validation_at(path))


def _validation_at(path):
    for value in (-1, 1.5, "1"):
        try:
            worker.run_batch([1], path, lambda item, key: item, max_items=value)
            return False
        except ValueError:
            pass
    return True


def no_mutation():
    def run(path):
        items = [{"nested": [1]}]
        before = copy.deepcopy(items)
        worker.run_batch(items, path, lambda item, key: item["nested"].append(2))
        return items == before
    return with_path(run)


record("one-shot", 10, one_shot)
record("split-resume", 20, split_resume)
record("stable-idempotency-keys", 10, stable_keys)
record("failure-resume", 15, failure_resume)
record("input-mismatch", 10, mismatch_rejected)
record("corrupt-checkpoint", 10, corrupt_rejected)
record("safe-exact-schema", 15, safe_schema)
record("atomic-cleanup", 5, atomic_cleanup)
record("argument-validation", 3, validation)
record("caller-no-mutation", 2, no_mutation)

score = sum(item["weight"] for item in checks if item["passed"])
print(json.dumps({"passed": score == 100, "score": score, "checks": checks}))
sys.exit(0 if score == 100 else 1)
