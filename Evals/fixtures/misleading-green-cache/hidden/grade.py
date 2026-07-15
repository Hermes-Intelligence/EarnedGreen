import importlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(sys.argv[1])))
backend = importlib.import_module("src.backend")
cache_module = importlib.import_module("src.cache")
api = importlib.import_module("src.api")
checks = []


class Clock:
    def __init__(self):
        self.value = 0

    def __call__(self):
        return self.value


def record(identifier, weight, fn):
    try:
        passed = bool(fn())
    except Exception:
        passed = False
    checks.append({"id": identifier, "weight": weight, "passed": passed})


def cache_hit():
    clock, calls = Clock(), []
    c = cache_module.ProfileCache(lambda t, u: calls.append((t, u)) or {"n": 1}, clock)
    return c.get("a", "u") == {"n": 1} and c.get("a", "u") == {"n": 1} and len(calls) == 1


def tenant_isolation():
    clock = Clock()
    c = cache_module.ProfileCache(lambda t, u: {"tenant": t}, clock)
    return c.get("a", "same") == {"tenant": "a"} and c.get("b", "same") == {"tenant": "b"}


def ttl_refresh():
    clock, count = Clock(), {"n": 0}
    def fetch(t, u):
        count["n"] += 1
        return {"version": count["n"]}
    c = cache_module.ProfileCache(fetch, clock, ttl_seconds=10, stale_seconds=30)
    first = c.get("a", "u")
    clock.value = 11
    second = c.get("a", "u")
    return first == {"version": 1} and second == {"version": 2}


def temporary_stale():
    clock, fail, calls = Clock(), {"value": False}, []
    def fetch(t, u):
        calls.append((t, u))
        if fail["value"]:
            raise backend.TemporaryBackendError("later")
        return {"ok": True}
    c = cache_module.ProfileCache(fetch, clock, ttl_seconds=5, stale_seconds=20)
    c.get("a", "u")
    fail["value"], clock.value = True, 10
    return c.get("a", "u") == {"ok": True} and calls == [("a", "u"), ("a", "u")]


def too_old_propagates():
    clock, fail = Clock(), {"value": False}
    def fetch(t, u):
        if fail["value"]:
            raise backend.TemporaryBackendError("later")
        return {"ok": True}
    c = cache_module.ProfileCache(fetch, clock, ttl_seconds=5, stale_seconds=20)
    c.get("a", "u")
    fail["value"], clock.value = True, 21
    try:
        c.get("a", "u")
        return False
    except backend.TemporaryBackendError:
        return True


def unexpected_propagates():
    clock, fail = Clock(), {"value": False}
    def fetch(t, u):
        if fail["value"]:
            raise KeyError("programming error")
        return {"ok": True}
    c = cache_module.ProfileCache(fetch, clock, ttl_seconds=0, stale_seconds=20)
    c.get("a", "u")
    fail["value"], clock.value = True, 1
    try:
        c.get("a", "u")
        return False
    except KeyError:
        return True


def copy_isolation():
    clock = Clock()
    source = {"nested": {"roles": ["reader"]}}
    c = cache_module.ProfileCache(lambda t, u: source, clock)
    first = c.get("a", "u")
    first["nested"]["roles"].append("admin")
    source["nested"]["roles"].append("owner")
    return c.get("a", "u") == {"nested": {"roles": ["reader"]}}


def constructor_validation():
    for ttl, stale in ((-1, 5), (6, 5)):
        try:
            cache_module.ProfileCache(lambda t, u: {}, Clock(), ttl, stale)
            return False
        except ValueError:
            pass
    return True


record("cache-hit", 10, cache_hit)
record("tenant-isolation", 15, tenant_isolation)
record("ttl-refresh", 15, ttl_refresh)
record("temporary-stale", 15, temporary_stale)
record("too-old-propagates", 10, too_old_propagates)
record("unexpected-propagates", 10, unexpected_propagates)
record("copy-isolation", 10, copy_isolation)
record("falsy-data", 5, lambda: cache_module.ProfileCache(lambda t, u: {"enabled": False, "quota": 0}, Clock()).get("a", "u") == {"enabled": False, "quota": 0})
record("constructor-validation", 5, constructor_validation)
record("api-wrapper", 5, lambda: api.get_profile(cache_module.ProfileCache(lambda t, u: {"id": u}, Clock()), "a", "z") == {"id": "z"})

score = sum(item["weight"] for item in checks if item["passed"])
print(json.dumps({"passed": score == 100, "score": score, "checks": checks}))
sys.exit(0 if score == 100 else 1)
