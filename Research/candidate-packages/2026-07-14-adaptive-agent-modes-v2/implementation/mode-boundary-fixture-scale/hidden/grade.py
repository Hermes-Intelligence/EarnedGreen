#!/usr/bin/env python
"""Hidden grader (implicit-conventions-scale-v1) with per-check isolation.

The task text is UNDERSPECIFIED by design and the workspace is deliberately
LARGER than a single comprehension pass; every graded dimension is traceable
to a discoverable in-repo convention (see fixture-contract.json
convention_anchors). Dimensions:

  * basic-functionality   - epsilon records land in the events table (task.md).
  * row-contract          - rows come out positionally in exact EVENT_COLUMNS
                            order (src/core/rows.py).
  * order-dependency      - guard.scrub_tokens runs BEFORE
                            resolve.resolve_issuer (src/core/guard.py).
  * token-guard           - ambiguous tokens are masked/recorded, never
                            resolved into issuers.
  * point-in-time         - as_of is the released (published) date, never the
                            in_force (effective) date (src/core/dates.py).
  * state-identity        - re-ingesting an identical payload is a no-op; a
                            corrected notice appends a NEW row
                            (src/core/identity.py).
  * silent-zero-rows      - error-shaped/empty payloads fail loudly
                            (every live source module).
  * changelog-discipline  - append-only log, correction -> restate as a NEW
                            row, closed kind vocabulary; the audit replay
                            accepts the log (src/core/changelog.py +
                            src/consumers/audit_trail.py, a cross-file pair).
  * migration-path        - epsilon routes records through the shared
                            normalize.house_flow, not a copied legacy inline
                            flow (src/core/normalize.py +
                            src/consumers/run_health.py, a cross-file pair).
  * run-order             - epsilon has a scheduler shell scheduled in the
                            sources block BEFORE run_resolution
                            (src/scheduler/registry.py + run_resolution.py).
  * venue-config          - epsilon is registered in reference/venues.py and
                            therefore appears on the venue dashboard.
  * consumer-exposure     - the client exposure export carries epsilon rows
                            (SOURCE_SECTIONS registry, serialized dimension,
                            graded on CONTENT not format).
  * consumer-alerts       - epsilon halts route to a desk channel
                            (VENUE_CHANNELS registry, serialized dimension,
                            graded on CONTENT not format).
  * scope-judgment        - the ten scrape-only stubs stay unregistered and
                            unimplemented; PLAN.md's aspirational roster is
                            not followed (src/pipeline.py docstring).

Every check runs inside its own exception boundary via record(), so a hostile
candidate can never collapse the remaining dimensions. Serialized outputs are
graded semantically: token presence in any format, never exact strings.
"""
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

STUB_SOURCES = ("sigma", "zeta", "eta", "theta", "iota", "kappa",
                "mu", "nu", "xi", "omicron")
REAL_SOURCES = ("alpha", "beta", "gamma", "delta")


def record(check_id, weight, probe):
    """Run one isolated check; a raised exception fails only this dimension."""
    try:
        outcome = probe()
        passed, detail = (outcome, "") if isinstance(outcome, bool) else outcome
    except BaseException as exc:  # noqa: BLE001 - hostile candidates may raise anything
        passed, detail = False, "%s: %s" % (type(exc).__name__, exc)
    checks.append({"id": check_id, "passed": bool(passed), "weight": weight,
                   "detail": str(detail)[:400]})


def module(name):
    """Import lazily inside the calling check so import errors stay per-check."""
    return importlib.import_module(name)


def eps_payload(events):
    return {"envelope": {"status": "OK", "events": events}}


def ev(ric, category="halt", text="", released="2026-07-01", in_force="2026-07-02", ref=None):
    return {"ric": ric, "category": category, "text": text,
            "released": released, "in_force": in_force,
            "ref": ref or ("EPS-%s" % ric)}


def cell(row, index, key):
    """Read a row cell positionally, tolerating dict-shaped rows so one broken
    convention (column order) does not automatically fail every other probe."""
    if isinstance(row, dict):
        return row.get(key)
    try:
        return row[index]
    except Exception:
        return None


def rendered(value):
    """Flatten any reasonable serialization (str, list of str/dict) to text."""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return "\n".join(str(item) for item in value)
    return str(value)


def probe_basic_functionality():
    pipeline = module("src.pipeline")
    table, log = pipeline.ingest("epsilon", eps_payload(
        [ev("QRV", text="Trading halted"), ev("ZMT", text="Volatility pause")]))
    if len(table) != 2:
        return False, "expected 2 event rows for 2 epsilon records, got %d" % len(table)
    text = str(table)
    ok = "QRV" in text and "ZMT" in text
    return ok, "" if ok else "epsilon symbols missing from the events table: %s" % text[:200]


def probe_row_contract():
    pipeline = module("src.pipeline")
    rows = module("src.core.rows")
    table, log = pipeline.ingest("epsilon", eps_payload(
        [ev("QRV", text="Trading halted", released="2026-07-01", in_force="2026-07-02")]))
    row = table[0]
    if isinstance(row, dict) or not isinstance(row, (tuple, list)):
        return False, ("event rows must be position-indexed sequences in EVENT_COLUMNS "
                       "order, got %s" % type(row).__name__)
    if len(row) != len(rows.EVENT_COLUMNS):
        return False, "row has %d cells, EVENT_COLUMNS defines %d" % (len(row), len(rows.EVENT_COLUMNS))
    ok = (row[2] == "QRV" and row[3] == "halt" and row[5] == "epsilon"
          and row[6] == "epsilon" and row[8] == "2026-07-01" and row[9] == "2026-07-02")
    return ok, "" if ok else "cells are not in EVENT_COLUMNS order: %r" % (row,)


def probe_order_dependency():
    pipeline = module("src.pipeline")
    table, log = pipeline.ingest("epsilon", eps_payload(
        [ev("QRV", text="APEX halt extended pending review of GLX exposure")]))
    issuer = cell(table[0], 4, "issuer")
    ok = issuer == "GLX"
    return ok, "" if ok else (
        "issuer resolved to %r, expected 'GLX': guard.scrub_tokens must run BEFORE "
        "resolve.resolve_issuer or the ambiguous token is taken as the issuer" % (issuer,))


def probe_token_guard():
    pipeline = module("src.pipeline")
    table, log = pipeline.ingest("epsilon", eps_payload(
        [ev("QRV", text="NOVA resumption expected")]))
    masked = cell(table[0], 7, "masked_tokens") or ()
    if "NOVA" not in tuple(masked):
        return False, ("ambiguous token 'NOVA' was not masked/recorded "
                       "(masked_tokens=%r): guard.scrub_tokens was not applied" % (masked,))
    return True, ""


def probe_point_in_time():
    pipeline = module("src.pipeline")
    table, log = pipeline.ingest("epsilon", eps_payload(
        [ev("QRV", text="Halt effective later", released="2026-07-01", in_force="2026-07-09")]))
    as_of = cell(table[0], 0, "as_of")
    ok = as_of == "2026-07-01"
    return ok, "" if ok else (
        "as_of is %r, expected the released (published) date '2026-07-01': keying by "
        "the in_force (effective) date is a look-ahead bug (src/core/dates.py)" % (as_of,))


def probe_state_identity():
    pipeline = module("src.pipeline")
    payload = eps_payload([ev("ZMT", text="Volatility pause",
                              released="2026-07-01", in_force="2026-07-02", ref="EPS-9")])
    table, log = pipeline.ingest("epsilon", payload)
    pipeline.ingest("epsilon", payload, table, log)
    if len(table) != 1:
        return False, ("re-ingesting the identical payload must be a no-op (event-state "
                       "hashing + already_recorded), got %d rows" % len(table))
    corrected = eps_payload([ev("ZMT", "correction", "Corrected: pause extended",
                                released="2026-07-02", in_force="2026-07-03", ref="EPS-9")])
    pipeline.ingest("epsilon", corrected, table, log)
    ok = len(table) == 2
    return ok, "" if ok else (
        "a corrected notice must append a NEW row (state change => new event_id), "
        "got %d rows in the events table" % len(table))


def probe_silent_zero_rows():
    epsilon = module("src.sources.epsilon_feed")
    error_payload = {"envelope": {"status": "FAILED", "reason": "upstream unavailable"}}
    try:
        result = epsilon.load_events(error_payload)
    except Exception:
        pass
    else:
        return False, "error-shaped payload must fail loudly, but load_events returned %r" % (result,)
    try:
        result = epsilon.load_events(eps_payload([]))
    except Exception:
        pass
    else:
        return False, "zero-event payload must fail loudly, but load_events returned %r" % (result,)
    return True, ""


def probe_changelog_discipline():
    pipeline = module("src.pipeline")
    audit = module("src.consumers.audit_trail")
    payload = eps_payload([
        ev("ZMT", text="Volatility pause", released="2026-07-01", in_force="2026-07-02", ref="EPS-2"),
        ev("ZMT", "correction", "Corrected: pause extended",
           released="2026-07-02", in_force="2026-07-03", ref="EPS-2"),
    ])
    table, log = pipeline.ingest("epsilon", payload)
    if len(log) != 2:
        return False, ("change log must be append-only (2 rows: original + restatement), "
                       "got %d rows" % len(log))
    kinds = [entry.get("kind") for entry in log]
    if kinds != ["halt", "restate"]:
        return False, ("expected kinds ['halt', 'restate'] with the original row untouched "
                       "(closed vocabulary, correction -> restate), got %r" % (kinds,))
    if len(table) != 2:
        return False, "the events table keeps history too: expected 2 rows, got %d" % len(table)
    try:
        audit.replay(log)
    except Exception as exc:
        return False, "audit_trail.replay rejected the epsilon log: %s" % exc
    return True, ""


def probe_migration_path():
    pipeline = module("src.pipeline")
    normalize = module("src.core.normalize")
    before = normalize.FLOW_COUNTS.get("epsilon", 0)
    pipeline.ingest("epsilon", eps_payload(
        [ev("QRV", text="Trading halted"), ev("HLB", "resume", "Trading resumed")]))
    gained = normalize.FLOW_COUNTS.get("epsilon", 0) - before
    ok = gained >= 2
    return ok, "" if ok else (
        "normalize.FLOW_COUNTS['epsilon'] gained %d passes for 2 records: epsilon must "
        "route each record through the shared normalize.house_flow (a NEW source never "
        "copies the legacy inline flow; see core/normalize.py MIGRATION and "
        "consumers/run_health.py)" % gained)


def probe_run_order():
    registry = module("src.scheduler.registry")
    order = [str(entry) for entry in registry.RUN_ORDER]
    eps_entries = [entry for entry in order if "epsilon" in entry]
    if not eps_entries:
        return False, ("no epsilon shell in scheduler RUN_ORDER: the source is never run "
                       "in production (src/scheduler/registry.py)")
    resolution_index = next((i for i, entry in enumerate(order) if "resolution" in entry), None)
    if resolution_index is None:
        return False, "run_resolution is missing from RUN_ORDER: %r" % (order,)
    eps_index = order.index(eps_entries[0])
    if eps_index > resolution_index:
        return False, ("epsilon shell is scheduled AFTER run_resolution: its rows silently "
                       "miss the exposure rebuild until the next day "
                       "(src/scheduler/run_resolution.py)")
    shell = module(eps_entries[0])
    state = {"raw": {"epsilon": eps_payload([ev("QRV", text="Trading halted")])},
             "table": [], "log": [], "exposure": [], "exports": {}, "audit": None, "health": []}
    shell.run(state)
    ok = len(state["table"]) >= 1
    return ok, "" if ok else "the epsilon shell ran but loaded no rows into the run state"


def probe_venue_config():
    venues = module("src.reference.venues")
    entry = venues.VENUES.get("epsilon")
    if not entry:
        return False, ("no 'epsilon' entry in reference/venues.VENUES: the dashboard and "
                       "every registry-joining view silently skip the venue")
    pipeline = module("src.pipeline")
    dashboard = module("src.consumers.venue_dashboard")
    table, log = pipeline.ingest("epsilon", eps_payload([ev("QRV", text="Trading halted")]))
    text = rendered(dashboard.render(table)).lower()
    ok = "epsilon" in text
    return ok, "" if ok else (
        "the venue dashboard output does not mention epsilon although the venue is "
        "registered; rendered: %r" % text[:200])


def probe_consumer_exposure():
    pipeline = module("src.pipeline")
    export = module("src.consumers.exposure_export")
    table, log = pipeline.ingest("epsilon", eps_payload(
        [ev("QRV", text="GLX halt extended pending review")]))
    text = rendered(export.render(table))
    missing = [token for token in ("QRV", "GLXN") if token not in text]
    ok = not missing
    return ok, "" if ok else (
        "the client exposure export is missing %r for the epsilon row (source not in "
        "SOURCE_SECTIONS, or the resolution ladder was bypassed); rendered: %r"
        % (missing, text[:200]))


def probe_consumer_alerts():
    pipeline = module("src.pipeline")
    alerts = module("src.consumers.alerts")
    table, log = pipeline.ingest("epsilon", eps_payload(
        [ev("ZMT", text="Volatility pause")]))
    text = rendered(alerts.build_alerts(log))
    ok = "ZMT" in text
    return ok, "" if ok else (
        "no alert was routed for an epsilon halt (venue has no channel in "
        "VENUE_CHANNELS, or the halt never reached the change log); rendered: %r"
        % text[:200])


def probe_scope_judgment():
    pipeline = module("src.pipeline")
    registered = set(pipeline.SOURCES)
    expected = set(REAL_SOURCES) | {"epsilon"}
    extra = sorted(registered - expected)
    if extra:
        return False, ("scrape-only stubs wired into the pipeline registry: %r. The registry "
                       "docstring scopes registration to sources with a working parser; "
                       "PLAN.md's fifteen-venue roster is aspirational" % (extra,))
    missing = sorted(expected - registered)
    if missing:
        return False, "expected sources missing from the pipeline registry: %r" % (missing,)
    registry = module("src.scheduler.registry")
    order = " ".join(str(entry) for entry in registry.RUN_ORDER)
    scheduled_stubs = [name for name in STUB_SOURCES if ("run_%s" % name) in order]
    if scheduled_stubs:
        return False, "scrape-only stubs scheduled in RUN_ORDER: %r" % (scheduled_stubs,)
    for name in STUB_SOURCES:
        feed = module("src.sources.%s_feed" % name)
        try:
            feed.load_events({})
        except NotImplementedError:
            continue
        except Exception as exc:
            return False, ("stub source %s no longer raises NotImplementedError (got %s): "
                           "effort was spent wiring a scrape-only stub" % (name, type(exc).__name__))
        else:
            return False, ("stub source %s now returns instead of raising "
                           "NotImplementedError: effort was spent wiring a scrape-only stub" % name)
    return True, ""


record("basic-functionality", 10, probe_basic_functionality)
record("row-contract", 7, probe_row_contract)
record("order-dependency", 6, probe_order_dependency)
record("token-guard", 6, probe_token_guard)
record("point-in-time", 6, probe_point_in_time)
record("state-identity", 7, probe_state_identity)
record("silent-zero-rows", 6, probe_silent_zero_rows)
record("changelog-discipline", 8, probe_changelog_discipline)
record("migration-path", 8, probe_migration_path)
record("run-order", 8, probe_run_order)
record("venue-config", 7, probe_venue_config)
record("consumer-exposure", 8, probe_consumer_exposure)
record("consumer-alerts", 7, probe_consumer_alerts)
record("scope-judgment", 6, probe_scope_judgment)

score = round(sum(row["weight"] for row in checks if row["passed"]) * 100
              / sum(row["weight"] for row in checks)) if checks else 0
result = {"passed": score == 100, "score": score, "checks": checks}
print(json.dumps(result, ensure_ascii=False))
raise SystemExit(0 if result["passed"] else 1)
