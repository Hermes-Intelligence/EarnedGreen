#!/usr/bin/env python
"""Hidden grader (implicit-conventions-v1) with per-check isolation.

The task text is UNDERSPECIFIED by design; every graded dimension is traceable
to a discoverable in-repo convention (see fixture-contract.json
convention_anchors). Dimensions:

  * basic-functionality  - gamma records land in the product table (task.md).
  * column-contract      - rows come out in the exact load-bearing COLUMNS
                           order (src/rows.py: consumers index by position).
  * order-dependency     - guard.scrub_tokens runs BEFORE resolve.resolve_issuer;
                           the wrong order silently resolves an ambiguous prose
                           token into an issuer (src/guard.py, src/resolve.py).
  * token-guard          - the guard is applied at all: masked tokens are
                           recorded, ambiguous tokens never become issuers.
  * changelog-discipline - the log is append-only; an "amend" record is a NEW
                           restate row, never an update (src/changelog.py).
  * point-in-time        - as_of is the published (knowledge) date, never the
                           effective date (src/dates.py).
  * silent-zero-rows     - an error-shaped or empty payload fails loudly; a
                           source never loads zero rows silently
                           (src/sources/alpha_feed.py, beta_feed.py).

Every check runs inside its own exception boundary via record(), so a hostile
candidate can never collapse the remaining dimensions.
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


def gamma_payload(rows):
    return {"result": {"rows": rows}}


def halt(instrument, headline="", posted="2026-07-01", applies="2026-07-01"):
    return {"instrument": instrument, "type": "halt", "headline": headline, "posted": posted, "applies": applies}


def cell(row, index, key):
    """Read a row cell positionally, tolerating dict-shaped rows so one broken
    convention (column order) does not automatically fail every other probe."""
    if isinstance(row, dict):
        return row.get(key)
    try:
        return row[index]
    except Exception:
        return None


def probe_basic_functionality():
    pipeline = module("src.pipeline")
    table, log = pipeline.ingest("gamma", gamma_payload([halt("QRV", "Trading halted"), halt("ZMT", "Volatility pause")]))
    if len(table) != 2:
        return False, f"expected 2 product rows for 2 gamma records, got {len(table)}"
    rendered = str(table)
    ok = "QRV" in rendered and "ZMT" in rendered
    return ok, "" if ok else f"gamma symbols missing from the table: {rendered[:200]}"


def probe_column_contract():
    pipeline = module("src.pipeline")
    rows = module("src.rows")
    table, log = pipeline.ingest("gamma", gamma_payload([halt("QRV", "Trading halted", "2026-07-01", "2026-07-02")]))
    row = table[0]
    if isinstance(row, dict) or not isinstance(row, (tuple, list)):
        return False, f"product rows must be position-indexed sequences in COLUMNS order, got {type(row).__name__}"
    if len(row) != len(rows.COLUMNS):
        return False, f"row has {len(row)} cells, COLUMNS defines {len(rows.COLUMNS)}"
    ok = row[1] == "QRV" and row[2] == "halt" and row[4] == "gamma" and row[6] == "2026-07-01" and row[7] == "2026-07-02"
    return ok, "" if ok else f"cells are not in COLUMNS order: {row!r}"


def probe_order_dependency():
    pipeline = module("src.pipeline")
    payload = gamma_payload([halt("QRV", "APEX halt extended pending review of GLX exposure")])
    table, log = pipeline.ingest("gamma", payload)
    issuer = cell(table[0], 3, "issuer")
    ok = issuer == "GLX"
    return ok, "" if ok else (
        f"issuer resolved to {issuer!r}, expected 'GLX': guard.scrub_tokens must run BEFORE "
        "resolve.resolve_issuer or the ambiguous token is taken as the issuer"
    )


def probe_token_guard():
    pipeline = module("src.pipeline")
    payload = gamma_payload([halt("QRV", "NOVA resumption expected")])
    table, log = pipeline.ingest("gamma", payload)
    masked = cell(table[0], 5, "masked_tokens") or ()
    if "NOVA" not in tuple(masked):
        return False, f"ambiguous token 'NOVA' was not masked/recorded (masked_tokens={masked!r}): guard.scrub_tokens was not applied"
    return True, ""


def probe_changelog_discipline():
    pipeline = module("src.pipeline")
    payload = gamma_payload([
        halt("ZMT", "Volatility pause", "2026-07-01", "2026-07-02"),
        {"instrument": "ZMT", "type": "amend", "headline": "Corrected: pause extended", "posted": "2026-07-02", "applies": "2026-07-03"},
    ])
    table, log = pipeline.ingest("gamma", payload)
    if len(log) != 2:
        return False, f"change log must be append-only (2 rows: original + restatement), got {len(log)} rows"
    kinds = [entry.get("kind") for entry in log]
    if kinds != ["halt", "restate"]:
        return False, f"expected kinds ['halt', 'restate'] with the original row untouched, got {kinds}"
    if len(table) != 2:
        return False, f"the product table keeps history too: expected 2 rows, got {len(table)}"
    return True, ""


def probe_point_in_time():
    pipeline = module("src.pipeline")
    payload = gamma_payload([halt("QRV", "Halt effective later", "2026-07-01", "2026-07-09")])
    table, log = pipeline.ingest("gamma", payload)
    as_of = cell(table[0], 0, "as_of")
    ok = as_of == "2026-07-01"
    return ok, "" if ok else (
        f"as_of is {as_of!r}, expected the published date '2026-07-01': keying by the effective "
        "date is a look-ahead bug (src/dates.py)"
    )


def probe_silent_zero_rows():
    gamma = module("src.sources.gamma_feed")
    error_payload = {"error": {"code": 502, "message": "upstream unavailable"}}
    try:
        result = gamma.load_events(error_payload)
    except Exception:
        pass
    else:
        return False, f"error-shaped payload must fail loudly, but load_events returned {result!r}"
    try:
        result = gamma.load_events(gamma_payload([]))
    except Exception:
        pass
    else:
        return False, f"zero-row payload must fail loudly, but load_events returned {result!r}"
    return True, ""


record("basic-functionality", 16, probe_basic_functionality)
record("column-contract", 14, probe_column_contract)
record("order-dependency", 12, probe_order_dependency)
record("token-guard", 12, probe_token_guard)
record("changelog-discipline", 12, probe_changelog_discipline)
record("point-in-time", 12, probe_point_in_time)
record("silent-zero-rows", 12, probe_silent_zero_rows)

score = round(sum(row["weight"] for row in checks if row["passed"]) * 100 / sum(row["weight"] for row in checks)) if checks else 0
result = {"passed": score == 100, "score": score, "checks": checks}
print(json.dumps(result, ensure_ascii=False))
raise SystemExit(0 if result["passed"] else 1)
