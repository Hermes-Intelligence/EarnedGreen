#!/usr/bin/env python
"""Hidden grader (v4) with per-check isolation and SEMANTIC serialization checks.

Every declared dimension is evaluated inside its own exception boundary via
`record(check_id, weight, probe)` and is always reported, so one early failure
(import bomb, first-call exception, wrong return type) can never collapse the
remaining dimensions into a single result.

Serialization dimensions are graded SEMANTICALLY, not by exact-string equality.
The v4 main-stage ablation exposed that the previous grader hard-compared
serialized lines against three arbitrary, mutually-inconsistent formats the task
never pins (render `customer:2`, exporter `3:customer:1:['n']`, snapshot
`v3|account|7|['m']`). Every executed arm did the work in SUBSTANCE -- routed the
consumer through `normalize_event`, applied the registry, and carried
`schema_version` -- but each chose a different delimiter/placement and so scored
an identical 70, measuring formatting rather than correctness. These probes now
parse each line tolerantly and assert the required CONTENT (entity_type,
entity_id, attribute keys, registry application, schema_version presence) while
STILL rejecting solutions that genuinely omit that content (legacy path, missing
version, dropped registry key).

Three dimensions are deliberately discriminating and aimed at the demonstrated
model blind spot (multi-hop / indirect downstream propagation and state-tracing):

  * exporter-propagation (Chain A) - the audit-export consumer
    exporter.export_digest -> serializer.serialize -> normalize_event.
  * snapshot-propagation (Chain B) - a SEPARATE indirect consumer
    snapshot.build_snapshot -> digest_helper.digest_line -> normalize_event.
  * repeat-dedup - a state interaction across a re-run: the unknown-type
    telemetry is per identity, so a replayed unresolved event counts
    `unknown_repeat`, never `unknown_entity_type` a second time.

The other ten dimensions are straightforwardly solvable and keep the task fair.
"""
import copy
import importlib
import json
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

WORKSPACE = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(WORKSPACE))

checks = []

# Runs of Unicode word characters, minus the underscore. Splits a serialized
# line into content tokens regardless of the delimiter/prefix style around them,
# so `3:customer:1:['n']`, `customer:1:['n']:3`, `customer:1:v3:['n']` and
# `customer@1 keys=[n] schema=3` all yield the tokens {customer, 1, n, ...}.
_WORD = re.compile(r"[^\W_]+", re.UNICODE)


def _tokens(text):
    return set(_WORD.findall(str(text)))


def _carries_version(text, version=3):
    """True if the schema_version integer appears as a standalone number in any
    format (`3:`, `:3`, `v3|`, `version=3`, `schema=3`, ...). A larger number
    that merely contains the digit does not count, and a line that omits the
    version entirely (the legacy path) fails."""
    return re.search(r"(?<!\d)" + str(version) + r"(?!\d)", str(text)) is not None


def _line_ok(line, entity_type, entity_id, keys, need_version=True):
    """Tolerantly verify one serialized line encodes the required content.

    Delimiter, prefix placement and separator style are all free; what must be
    present is the entity_type token, the entity_id token, every attribute key
    token, and (for the schema-versioned consumers) a standalone schema_version.
    """
    toks = _tokens(line)
    missing = []
    if entity_type not in toks:
        missing.append(f"entity_type {entity_type!r}")
    if entity_id not in toks:
        missing.append(f"entity_id {entity_id!r}")
    for key in keys:
        if key not in toks:
            missing.append(f"attribute-key {key!r}")
    if need_version and not _carries_version(line, 3):
        missing.append("schema_version 3")
    return (not missing), missing


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


# --- Straightforwardly solvable dimensions -------------------------------------

def probe_current_envelope():
    contracts = module("src.contracts")
    current = contracts.normalize_event(
        {"type": "customer", "id": "1", "fields": {"x": 1}},
        {"customer": lambda value: {**value, "ok": True}},
    )
    expected = {"entity_type": "customer", "entity_id": "1", "attributes": {"x": 1, "ok": True}, "schema_version": 3}
    return current == expected, "" if current == expected else f"got {current!r}"


def probe_open_world_unicode():
    contracts = module("src.contracts")
    metrics = module("src.metrics")
    metrics.reset()
    unknown = contracts.normalize_event({"type": "żółw-新", "id": "u", "fields": {"Δ": "✓"}}, {})
    expected = {"entity_type": "żółw-新", "entity_id": "u", "attributes": {"Δ": "✓"}, "schema_version": 3}
    if unknown != expected:
        return False, f"registry miss must pass through unchanged, got {unknown!r}"
    count = metrics.COUNTERS.get("unknown_entity_type")
    return count == 1, "" if count == 1 else f"unknown_entity_type counter is {count!r}, expected 1"


INVALID_EVENTS = (
    None,
    [],
    {"type": " ", "id": "x", "fields": {}},
    {"type": "x", "id": " ", "fields": {}},
    {"type": "x", "id": "1", "fields": []},
    {"type": "x", "id": "1", "fields": {}, "extra": 1},
    {"type": "x", "id": "1"},
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
    return legacy == expected, "" if legacy == expected else f"parse_record must keep its legacy 3-key shape, got {legacy!r}"


def probe_consumer_primary():
    """Semantic: render output must encode {entity_type, entity_id} (and the
    audit key list) in ANY format. schema_version is NOT pinned in the render
    string, so it is accepted whether present or absent."""
    consumers = module("src.consumers")
    primary = consumers.render_primary({"type": "customer", "id": "2", "fields": {}}, {})
    audit = consumers.render_audit({"type": "customer", "id": "2", "fields": {"b": 1}}, {})
    ptoks = _tokens(primary)
    if "customer" not in ptoks or "2" not in ptoks:
        return False, f"render_primary must encode entity_type and entity_id in some format, got {primary!r}"
    atoks = _tokens(audit)
    missing = [token for token in ("customer", "b") if token not in atoks]
    if missing:
        return False, f"render_audit must encode entity_type and the attribute key list, missing {missing}, got {audit!r}"
    return True, ""


def probe_documentation():
    readme = (WORKSPACE / "README.md").read_text(encoding="utf-8").lower()
    ok = "registry" in readme and "open" in readme and ("compat" in readme or "legacy" in readme)
    return ok, "" if ok else "README.md does not document the registry extension path and compatibility behavior"


def probe_degraded_path():
    """Omission-prone (solvable): a handler that raises is contained, counted, and not rejected."""
    contracts = module("src.contracts")
    metrics = module("src.metrics")
    metrics.reset()

    def boom(attrs):
        raise RuntimeError("handler failure on this input")

    result = contracts.normalize_event({"type": "flaky", "id": "e1", "fields": {"k": "v"}}, {"flaky": boom})
    expected = {"entity_type": "flaky", "entity_id": "e1", "attributes": {"k": "v"}, "schema_version": 3}
    if result != expected:
        return False, f"handler-error fallback must return the original attributes, got {result!r}"
    handler_error = metrics.COUNTERS.get("handler_error")
    malformed = metrics.COUNTERS.get("malformed_event", 0)
    unknown = metrics.COUNTERS.get("unknown_entity_type", 0)
    if handler_error != 1:
        return False, f"handler_error counter is {handler_error!r}, expected 1"
    if malformed != 0:
        return False, f"handler-error path must not count malformed_event (got {malformed!r})"
    if unknown != 0:
        return False, f"handler-error path must not count unknown_entity_type (got {unknown!r})"
    return True, ""


def probe_exact_type_match():
    """Adversarial open-world (solvable): a trailing-space type is an unresolved type, not a trimmed match."""
    contracts = module("src.contracts")
    metrics = module("src.metrics")
    metrics.reset()
    result = contracts.normalize_event(
        {"type": "customer ", "id": "9", "fields": {"a": 1}},
        {"customer": lambda a: {**a, "touched": True}},
    )
    expected = {"entity_type": "customer ", "entity_id": "9", "attributes": {"a": 1}, "schema_version": 3}
    if result != expected:
        return False, f"'customer ' must not match handler 'customer' and must keep its exact type, got {result!r}"
    unknown = metrics.COUNTERS.get("unknown_entity_type")
    return unknown == 1, "" if unknown == 1 else f"a trailing-space type is an unresolved type; unknown_entity_type is {unknown!r}, expected 1"


# --- Discriminating dimensions (SEMANTIC serialization) ------------------------

def probe_exporter_propagation():
    """Chain A (downstream-propagation): exporter -> serializer -> normalize_event.

    Semantic: for each event the serialized line must (a) go through
    normalize_event so the registry handler is applied (the resolved event gains
    key 'n'), (b) carry the schema_version value 3 in some format, and (c) encode
    the correct entity_type, entity_id and attribute keys. The line format itself
    (delimiter, prefix placement) is free. A line on the legacy path -- no
    registry key, no version -- still fails.
    """
    exporter = module("src.exporter")
    registry = {"customer": lambda a: {**a, "n": 1}}
    events = [
        {"type": "customer", "id": "1", "fields": {}},   # resolved: handler adds key 'n'
        {"type": "ghost", "id": "2", "fields": {"z": 9}},  # unresolved: keeps key 'z'
    ]
    digest = exporter.export_digest(events, registry)
    if not isinstance(digest, (list, tuple)):
        return False, f"export_digest must return a serialized line per record, got {digest!r}"
    if len(digest) != len(events):
        return False, f"export_digest must return one line per record, got {digest!r}"
    ok, missing = _line_ok(digest[0], "customer", "1", ["n"])
    if not ok:
        return False, (f"audit line for the resolved event is missing {missing} "
                       f"(registry not applied or schema_version not carried): got {digest[0]!r}")
    ok, missing = _line_ok(digest[1], "ghost", "2", ["z"])
    if not ok:
        return False, f"audit line for the unresolved event is missing {missing}: got {digest[1]!r}"
    return True, ""


def probe_snapshot_propagation():
    """Chain B (downstream-propagation, separate intermediary): snapshot -> digest_helper -> normalize_event.

    Semantic in the same way as Chain A, through a DIFFERENT intermediary. The
    snapshot must be a dict keyed by entity id; each line must go through
    normalize_event (resolved event gains key 'm'), carry schema_version 3 in
    some format, and encode the correct type/id/attribute keys.
    """
    snapshot = module("src.snapshot")
    registry = {"account": lambda a: {**a, "m": 2}}
    events = [
        {"type": "account", "id": "7", "fields": {}},    # resolved: handler adds key 'm'
        {"type": "phantom", "id": "8", "fields": {"q": 5}},  # unresolved: keeps key 'q'
    ]
    snap = snapshot.build_snapshot(events, registry)
    if not isinstance(snap, dict):
        return False, f"build_snapshot must return a dict keyed by entity id, got {snap!r}"
    if set(snap) != {"7", "8"}:
        return False, f"snapshot must be keyed by entity id, got keys {sorted(snap)!r}"
    ok, missing = _line_ok(snap["7"], "account", "7", ["m"])
    if not ok:
        return False, (f"snapshot line for the resolved event is missing {missing} "
                       f"(registry not applied or schema_version not carried): got {snap['7']!r}")
    ok, missing = _line_ok(snap["8"], "phantom", "8", ["q"])
    if not ok:
        return False, f"snapshot line for the unresolved event is missing {missing}: got {snap['8']!r}"
    return True, ""


def probe_repeat_dedup():
    """State interaction across a re-run: a replayed unresolved event counts unknown_repeat, not unknown_entity_type twice."""
    contracts = module("src.contracts")
    metrics = module("src.metrics")
    metrics.reset()
    event = {"type": "wraith", "id": "rk-1", "fields": {"a": 1}}
    expected = {"entity_type": "wraith", "entity_id": "rk-1", "attributes": {"a": 1}, "schema_version": 3}
    first = contracts.normalize_event(event, {})
    second = contracts.normalize_event(copy.deepcopy(event), {})
    if first != expected:
        return False, f"first unresolved sighting must pass through unchanged, got {first!r}"
    if second != expected:
        return False, f"replayed unresolved sighting must still pass through unchanged, got {second!r}"
    unknown = metrics.COUNTERS.get("unknown_entity_type")
    repeat = metrics.COUNTERS.get("unknown_repeat")
    if unknown != 1:
        return False, f"a replayed unresolved identity must count unknown_entity_type once, got {unknown!r}"
    if repeat != 1:
        return False, f"the replayed sighting must count unknown_repeat exactly once, got {repeat!r}"
    return True, ""


record("current-envelope", 9, probe_current_envelope)
record("open-world-unicode", 6, probe_open_world_unicode)
record("input-validation", 9, probe_input_validation)
record("malformed-telemetry", 6, probe_malformed_telemetry)
record("copy-isolation", 7, probe_copy_isolation)
record("legacy-wrapper", 4, probe_legacy_wrapper)
record("consumer-primary", 6, probe_consumer_primary)
record("documentation", 4, probe_documentation)
record("degraded-path", 7, probe_degraded_path)
record("exact-type-match", 7, probe_exact_type_match)
record("exporter-propagation", 12, probe_exporter_propagation)
record("snapshot-propagation", 12, probe_snapshot_propagation)
record("repeat-dedup", 11, probe_repeat_dedup)

score = round(sum(row["weight"] for row in checks if row["passed"]) * 100 / sum(row["weight"] for row in checks)) if checks else 0
result = {"passed": score == 100, "score": score, "checks": checks}
print(json.dumps(result, ensure_ascii=False))
raise SystemExit(0 if result["passed"] else 1)
