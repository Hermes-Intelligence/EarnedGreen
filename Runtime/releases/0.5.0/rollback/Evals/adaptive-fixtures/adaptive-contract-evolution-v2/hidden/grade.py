#!/usr/bin/env python
"""Hidden grader with per-check isolation.

Every declared dimension is evaluated inside its own exception boundary and is
always reported, so one early failure (import bomb, first-call exception, wrong
return type) can never collapse the remaining dimensions into a single result.
"""
import copy
import importlib
import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

WORKSPACE = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(WORKSPACE))

checks = []


def record(check_id, weight, probe):
    """Run one isolated check; a raised exception fails only this dimension."""
    try:
        outcome = probe()
        passed, detail = (outcome, "") if isinstance(outcome, bool) else outcome
    except BaseException as exc:  # noqa: BLE001 - hostile candidates may raise anything
        passed, detail = False, f"{type(exc).__name__}: {exc}"
    checks.append({"id": check_id, "passed": bool(passed), "weight": weight, "detail": str(detail)[:400]})


def module(name):
    """Import lazily inside the calling check so import errors stay per-check."""
    return importlib.import_module(name)


def probe_current_envelope():
    contracts = module("src.contracts")
    current = contracts.normalize_event({"type": "customer", "id": "1", "fields": {"x": 1}}, {"customer": lambda value: {**value, "ok": True}})
    expected = {"entity_type": "customer", "entity_id": "1", "attributes": {"x": 1, "ok": True}}
    return current == expected, "" if current == expected else f"got {current!r}"


def probe_open_world_unicode():
    contracts = module("src.contracts")
    unknown = contracts.normalize_event({"type": "żółw-新", "id": "u", "fields": {"Δ": "✓"}}, {})
    expected = {"entity_type": "żółw-新", "entity_id": "u", "attributes": {"Δ": "✓"}}
    return unknown == expected, "" if unknown == expected else f"registry miss must pass through unchanged, got {unknown!r}"


def probe_unknown_telemetry():
    contracts = module("src.contracts")
    metrics = module("src.metrics")
    metrics.reset()
    try:
        contracts.normalize_event({"type": "żółw-新", "id": "u", "fields": {"Δ": "✓"}}, {})
    except (TypeError, ValueError):
        pass  # counted below either way; the miss counter is this dimension's oracle
    count = metrics.COUNTERS.get("unknown_entity_type")
    return count == 1, "" if count == 1 else f"unknown_entity_type counter is {count!r}, expected 1"


INVALID_EVENTS = (
    None,
    [],
    {"type": " ", "id": "x", "fields": {}},
    {"type": "x", "id": " ", "fields": {}},
    {"type": "x", "id": "1", "fields": []},
    {"type": "x", "id": "1", "fields": {}, "extra": 1},
)


def rejection_cases(contracts):
    """Yield callables that must each raise TypeError or ValueError."""
    for value in INVALID_EVENTS:
        yield lambda value=value: contracts.normalize_event(value, {})
    yield lambda: contracts.normalize_event({"type": "x", "id": "1", "fields": {}}, {"x": "not callable"})
    yield lambda: contracts.normalize_event({"type": "x", "id": "1", "fields": {}}, {"x": lambda attrs: "not a dict"})


def probe_input_validation():
    contracts = module("src.contracts")
    unrejected = 0
    for case in rejection_cases(contracts):
        try:
            case()
            unrejected += 1
        except (TypeError, ValueError):
            pass
    return unrejected == 0, "" if unrejected == 0 else f"{unrejected} malformed inputs were accepted instead of rejected"


def probe_malformed_telemetry():
    contracts = module("src.contracts")
    metrics = module("src.metrics")
    metrics.reset()
    attempts = 0
    for case in rejection_cases(contracts):
        attempts += 1
        try:
            case()
        except (TypeError, ValueError):
            pass
    count = metrics.COUNTERS.get("malformed_event", 0)
    return count == attempts, "" if count == attempts else f"malformed_event counter is {count!r}, expected {attempts} (one per rejection)"


def probe_copy_isolation():
    contracts = module("src.contracts")
    original = {"type": "customer", "id": "1", "fields": {"nested": {"x": 1}}}
    snapshot = copy.deepcopy(original)
    output = contracts.normalize_event(original, {"customer": lambda attrs: attrs})
    output["attributes"]["nested"]["x"] = 9
    return original == snapshot, "" if original == snapshot else "mutating the result changed caller-owned input"


def probe_legacy_wrapper():
    contracts = module("src.contracts")
    legacy = contracts.parse_record({"type": "legacy", "id": "l", "fields": {"x": 2}})
    expected = {"entity_type": "legacy", "entity_id": "l", "attributes": {"x": 2}}
    return legacy == expected, "" if legacy == expected else f"got {legacy!r}"


def probe_consumer_propagation():
    consumers = module("src.consumers")
    primary = consumers.render_primary({"type": "customer", "id": "2", "fields": {}}, {})
    audit = consumers.render_audit({"type": "customer", "id": "2", "fields": {"b": 1}}, {})
    ok = primary == "customer:2" and audit == "AUDIT customer ['b']"
    return ok, "" if ok else f"got primary={primary!r} audit={audit!r}"


def probe_documentation():
    readme = (WORKSPACE / "README.md").read_text(encoding="utf-8").lower()
    ok = "registry" in readme and "open" in readme and ("compat" in readme or "legacy" in readme)
    return ok, "" if ok else "README.md does not document the registry extension path and compatibility behavior"


record("current-envelope", 10, probe_current_envelope)
record("open-world-unicode", 15, probe_open_world_unicode)
record("unknown-telemetry", 10, probe_unknown_telemetry)
record("input-validation", 15, probe_input_validation)
record("malformed-telemetry", 5, probe_malformed_telemetry)
record("copy-isolation", 10, probe_copy_isolation)
record("legacy-wrapper", 10, probe_legacy_wrapper)
record("consumer-propagation", 10, probe_consumer_propagation)
record("documentation", 5, probe_documentation)

score = round(sum(row["weight"] for row in checks if row["passed"]) * 100 / sum(row["weight"] for row in checks)) if checks else 0
result = {"passed": score == 100, "score": score, "checks": checks}
print(json.dumps(result, ensure_ascii=False))
raise SystemExit(0 if result["passed"] else 1)
