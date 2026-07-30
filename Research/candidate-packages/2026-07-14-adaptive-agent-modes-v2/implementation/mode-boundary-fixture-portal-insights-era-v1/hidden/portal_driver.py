#!/usr/bin/env python3
"""Recording driver for the HermesPortal insights-era fixture.

DESIGN — every lesson of the dataflow campaigns built in from birth:
  * the OBSERVABLE surface is the DELIVERABLE: emitted JSON payloads, not DB
    traffic. Events are semantic payload facts (bucket order, aggregate
    values, edge tuples), value-bearing where the value IS the behaviour.
  * the db seam is stubbed at the documented function level
    (read_single_record / read_multiple_records — infrastructure the task
    forbids modifying), with SELECT-list projection, named-insert-free
    (read-only slice), and NO general SQL semantics: corpus calls only ever
    exercise `col = %s [AND col = %s ...]` conjunctions, simple ORDER BY,
    LIMIT/OFFSET, count(*) and the one GROUP BY country shape. Anything else
    is a NAMED totality finding.
  * bucket canonical ORDER is honoured by LITERAL RANKING: the quoted labels
    appearing in the query's ORDER BY clause, in order of appearance, rank the
    rows — CASE, array_position or any spelling that lists the labels works.
  * a LEFT JOIN LATERAL into vextrum.sources is emulated for the SQL path;
    a python-side two-query merge is equally served by plain equality
    lookups — both implementation shapes read the same canned state.

Usage: python portal_driver.py <corpus.json>; run from the WORKSPACE root.
Prints {scenario_id: [event, ...]} as one JSON line. Deterministic, offline.
"""
from __future__ import annotations

import json
import re
import sys
import types
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID

EVENTS: list[str] = []
STATE: dict = {}


# --- canned-value decoding ---------------------------------------------------------

def _decode(value):
    if isinstance(value, str):
        if value.startswith("@dt:"):
            return datetime.fromisoformat(value[4:].replace("Z", "+00:00"))
        if value.startswith("@dec:"):
            return Decimal(value[5:])
        if value.startswith("@uuid:"):
            return UUID(value[6:])
    if isinstance(value, list):
        return [_decode(v) for v in value]
    if isinstance(value, dict):
        return {k: _decode(v) for k, v in value.items()}
    return value


# --- projection helpers (ported from the dataflow v2.3 instrument) -----------------

def _token(expr: str) -> str:
    return expr.strip().split("::")[0].split(".")[-1].strip('"').strip().lower()


def _select_items(clause: str) -> list[tuple[str, str]]:
    items = []
    depth, current, parts = 0, [], []
    for ch in clause:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    parts.append("".join(current))
    for raw in (p.strip() for p in parts if p.strip()):
        alias_match = re.search(r"(?i)\s+as\s+([a-z0-9_\"]+)\s*$", raw)
        if alias_match:
            items.append((alias_match.group(1).strip('"').lower(), _token(raw[:alias_match.start()])))
        else:
            items.append((_token(raw), _token(raw)))
    return items


def _project(rows: list[dict], s: str) -> list[dict]:
    match = re.match(r"select\s+(?:distinct\s+)?(.*?)\s+from\s", s, re.S)
    if not match:
        return rows
    clause = match.group(1).strip()
    if clause == "*" or clause.endswith(".*"):
        return rows
    spec = _select_items(clause)
    out = []
    for row in rows:
        projected = {}
        for name, token in spec:
            if token in row:
                projected[name] = row[token]
            elif name in row:
                projected[name] = row[name]
            elif "count" in token:
                projected[name] = row.get("__count__", 0)
            else:
                EVENTS.append(f"err-unknown-column-{token}")
                raise RuntimeError(f"column {token!r} does not exist (see DATA.md)")
        out.append(projected)
    return out


# --- minimal read-only SQL evaluation ---------------------------------------------

def _mask_subqueries(s: str) -> str:
    """Blank parenthesized groups containing SELECT so outer-clause parsing
    (WHERE / ORDER BY) never trips over lateral/sub-select internals."""
    out, depth, buffer, stack = [], 0, [], []
    for ch in s:
        if ch == "(":
            depth += 1
            stack.append(len(buffer))
            buffer.append(ch)
        elif ch == ")" and depth:
            depth -= 1
            start = stack.pop()
            group = "".join(buffer[start:]) + ")"
            del buffer[start:]
            buffer.append("(SUBQ)" if "select" in group else group)
        else:
            buffer.append(ch)
    return "".join(buffer)


def _where_equalities(s: str, params: list) -> list[tuple[str, object]]:
    """Conjunctions of `col = %s` only; anything richer is a totality finding."""
    s = _mask_subqueries(s)
    where = re.search(r"\bwhere\b(.*?)(order by|group by|limit|$)", s, re.S)
    if not where:
        return []
    clause = where.group(1)
    # tolerate the guard-endpoint literal used by countries
    clause = clause.replace("country != ''", "").replace("country is not null", "")
    pieces = [p.strip() for p in re.split(r"\band\b", clause) if p.strip()]
    spec, index = [], 0
    for piece in pieces:
        eq = re.match(r"^\(?\s*([a-z0-9_.\"]+)\s*=\s*%s\s*\)?$", piece)
        if eq:
            spec.append((_token(eq.group(1)), params[index]))
            index += 1
            continue
        EVENTS.append("err-unsupported-predicate")
        raise RuntimeError(f"the harness evaluates only col = %s conjunctions here; got: {piece[:80]}")
    return spec


def _order_rows(rows: list[dict], s: str) -> list[dict]:
    s = _mask_subqueries(s)
    order = re.search(r"order by\s+(.*?)(limit|offset|$)", s, re.S)
    if not order:
        return rows
    clause = order.group(1).strip()
    literals = re.findall(r"'([a-z0-9_]+)'", clause)
    if literals:
        rank = {label: i for i, label in enumerate(dict.fromkeys(literals))}
        key_column = "bucket_label" if "bucket_label" in clause else None
        if key_column:
            return sorted(rows, key=lambda r: rank.get(str(r.get(key_column)), len(rank)))
    keys = []
    for part in clause.split(","):
        part = part.strip()
        m = re.match(r"^([a-z0-9_.\"]+)(\s+(asc|desc))?$", part)
        if not m:
            return rows  # complex expression: leave storage order (deterministic)
        keys.append((_token(m.group(1)), (m.group(3) or "asc") == "desc"))
    for column, descending in reversed(keys):
        rows = sorted(rows, key=lambda r: (r.get(column) is None, r.get(column)), reverse=descending)
    return rows


def _limit_offset(rows: list[dict], s: str, params: list) -> list[dict]:
    s = _mask_subqueries(s)
    limit = re.search(r"limit\s+(%s|\d+)", s)
    offset = re.search(r"offset\s+(%s|\d+)", s)
    lo = 0
    if offset:
        lo = params[-1] if offset.group(1) == "%s" else int(offset.group(1))
    rows = rows[lo:]
    if limit:
        n = None
        if limit.group(1) == "%s":
            n = params[-2] if offset and offset.group(1) == "%s" else params[-1]
        else:
            n = int(limit.group(1))
        rows = rows[:n]
    return rows


def _table_rows(name: str) -> list[dict]:
    return [dict(r) for r in STATE.get(name, [])]


def _query(sql: str, params) -> list[dict]:
    s = " ".join(sql.split()).lower()
    params = list(params or [])
    match = re.search(r"\bfrom\s+([a-z0-9_.\"]+)", s)
    primary = _token(match.group(1)) if match else ""

    tables = {"discovery_runs": "discovery_runs", "sources": "sources",
              "source_buckets": "source_buckets",
              "question_source_matrix": "question_source_matrix",
              "organizations": "organizations"}
    table = tables.get(primary)
    if table is None:
        EVENTS.append("err-unknown-table")
        raise RuntimeError(f"harness knows no table {primary!r} (see DATA.md)")

    # count LIMIT/OFFSET placeholders so WHERE param mapping stays aligned
    tail_params = len(re.findall(r"(limit|offset)\s+%s", s))
    where_params = params[:len(params) - tail_params] if tail_params else params
    rows = _table_rows(table)
    for column, value in _where_equalities(s, where_params):
        rows = [r for r in rows if str(r.get(column)) == str(value)]

    # the qsm LEFT JOIN LATERAL enrichment (SQL-path emulation)
    if table == "question_source_matrix" and "lateral" in s:
        lateral_spec = _select_items(re.search(r"lateral\s*\(\s*select\s+(.*?)\s+from", s, re.S).group(1))
        for row in rows:
            source = next((x for x in _table_rows("sources")
                           if str(x.get("run_id")) == str(row.get("run_id"))
                           and str(x.get("domain")) == str(row.get("domain"))), None)
            for name, token in lateral_spec:
                row[name] = source.get(token) if source else None

    if "group by" in s and table == "sources":
        counts: dict[str, int] = {}
        for row in rows:
            country = row.get("country")
            if country:
                counts[country] = counts.get(country, 0) + 1
        rows = [{"country": c, "count": n, "__count__": n} for c, n in sorted(counts.items())]
    elif "count(" in s:
        rows = [{"total": len(rows), "count": len(rows), "__count__": len(rows)}]

    rows = _order_rows(rows, s)
    rows = _limit_offset(rows, s, params)
    EVENTS.append(f"q-{table}")
    return _project(rows, s)


# --- seam stubs --------------------------------------------------------------------

def install_seams(workspace: Path) -> None:
    package = types.ModuleType("hermes_intelligence")
    package.__path__ = [str(workspace / "hermes_intelligence")]
    sys.modules["hermes_intelligence"] = package

    db = types.ModuleType("hermes_intelligence.db")
    db.read_multiple_records = lambda sql, params=None: _query(sql, params)
    db.read_single_record = lambda sql, params=None: (_query(sql, params) or [None])[0]
    db.execute_query = lambda sql, params=None: _query(sql, params)
    db.write_to_database = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("read-only slice"))
    db.update_database = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("read-only slice"))
    db._connect = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("read-only slice"))
    sys.modules["hermes_intelligence.db"] = db

    auth = types.ModuleType("hermes_intelligence.auth")
    auth.redirect_if_no_auth = lambda *a, **k: None
    auth.get_organization_from_token = lambda token: "org-1"
    auth.get_user_id_from_token = lambda token: "user-1"
    sys.modules["hermes_intelligence.auth"] = auth

    class _AccessContext:
        access_level = "internal"
        org_id = "org-1"

    access = types.ModuleType("hermes_intelligence.access_control")

    def _verify(token, *a, **k):
        rows = [r for r in _table_rows("organizations") if str(r.get("id")) == "org-1"]
        if not rows or not rows[0].get("vextrum_access") or not rows[0].get("is_internal"):
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail="Access denied")
        return _AccessContext()

    access.verify_internal_access = _verify
    access.verify_vextrum_access = _verify
    access.verify_universe_access = _verify
    access.fulfill_pregrants = lambda *a, **k: None
    sys.modules["hermes_intelligence.access_control"] = access

    services = types.ModuleType("hermes_intelligence.services")
    services.__path__ = []
    ecs = types.ModuleType("hermes_intelligence.services.ecs_dispatch")

    class EcsDispatchError(Exception):
        pass

    ecs.EcsDispatchError = EcsDispatchError
    ecs.trigger_ontology_generation = lambda *a, **k: {"status": "stubbed"}
    sys.modules["hermes_intelligence.services"] = services
    sys.modules["hermes_intelligence.services.ecs_dispatch"] = ecs

    class _Anything:
        def __call__(self, *a, **k):
            return _Anything()

        def __getattr__(self, name):
            return _Anything()

    for name in ("boto3", "httpx"):
        mod = types.ModuleType(name)
        mod.__getattr__ = lambda attr, _A=_Anything: _A()
        sys.modules[name] = mod
    botocore = types.ModuleType("botocore")
    config = types.ModuleType("botocore.config")
    config.Config = lambda *a, **k: object()
    botocore.config = config
    sys.modules["botocore"] = botocore
    sys.modules["botocore.config"] = config


# --- payload observation -----------------------------------------------------------

def _content(response):
    if hasattr(response, "body"):
        return json.loads(bytes(response.body).decode("utf-8"))
    return response


def observe(ep: str, payload: dict) -> None:
    EVENTS.append(f"keys-{ep}-" + "+".join(sorted(payload.keys())))
    if ep in ("buckets", "coverage"):
        for i, bucket in enumerate(payload.get("buckets", [])):
            EVENTS.append(f"bucket-{i}-{bucket.get('bucket_label')}")
        if payload.get("buckets"):
            EVENTS.append("bucketkeys-" + "+".join(sorted(payload["buckets"][0].keys())))
        for flag in payload.get("geographic_flags", []) or []:
            EVENTS.append(f"flag-{ep}-{flag}")
    if ep == "buckets":
        if "builder_method" in payload:
            EVENTS.append(f"qg-builder-{payload.get('builder_method')}")
        if "llm_calls_used" in payload:
            EVENTS.append(f"qg-calls-{payload.get('llm_calls_used')}")
        if "quality_gate_results" in payload:
            gates = payload.get("quality_gate_results") or []
            EVENTS.append(f"qg-results-n{len(gates)}")
            EVENTS.append(f"qg-alldict-{all(isinstance(g, dict) for g in gates)}")
    if ep == "coverage":
        coverage = payload.get("coverage", {})
        EVENTS.append(f"coverage-type-{type(coverage).__name__}")
        if isinstance(coverage, dict) and coverage:
            EVENTS.append("coverage-keys-" + "+".join(sorted(coverage.keys())))
    if ep == "matrix":
        for edge in payload.get("edges", []):
            score = edge.get("viability_score", "MISSINGKEY")
            stype = edge.get("source_type", "MISSINGKEY")
            EVENTS.append(f"edge-q{edge.get('question_number')}-{edge.get('domain')}"
                          f"-vs{score}-st{stype}")
    if ep == "sources":
        EVENTS.append(f"sources-n{len(payload.get('sources', []))}")
        for key in ("total", "page", "pages"):
            if key in payload:
                EVENTS.append(f"sources-{key}-n{payload[key]}")
    if ep in ("portfolio", "taxonomy", "briefing", "covmatrix", "countries"):
        EVENTS.append(f"payload-{ep}:" + json.dumps(payload, sort_keys=True, ensure_ascii=True))


ENDPOINTS = {
    "buckets": "get_run_buckets",
    "matrix": "get_question_source_matrix",
    "coverage": "get_coverage_report",
    "sources": "get_run_sources",
    "portfolio": "get_portfolio_analysis",
    "taxonomy": "get_tag_taxonomy",
    "briefing": "get_strategic_briefing",
    "covmatrix": "get_coverage_matrix",
    "countries": "get_run_countries",
}


def run_call(module, call: dict) -> None:
    ep = call["ep"]
    function = getattr(module, ENDPOINTS[ep], None)
    if function is None:
        EVENTS.append(f"end-{ep}-raise-AttributeError")
        return
    kwargs = dict(call.get("kwargs") or {})
    kwargs.setdefault("token", "fixture-token")
    # direct function calls bypass FastAPI's dependency layer: unwrap
    # Query(...)/Header(...) defaults to their underlying values so unpassed
    # params behave exactly as an HTTP request without them
    import inspect
    for name, parameter in inspect.signature(function).parameters.items():
        if name in kwargs or parameter.default is inspect.Parameter.empty:
            continue
        default = parameter.default
        if hasattr(default, "default"):
            kwargs[name] = default.default
    try:
        payload = _content(function(call.get("run_id", "r-1"), **kwargs))
        observe(ep, payload)
        EVENTS.append(f"end-{ep}-ok")
    except Exception as error:  # noqa: BLE001 - the ending IS the observable
        status = getattr(error, "status_code", None)
        if status is not None:
            EVENTS.append(f"http-{ep}-{status}")
        else:
            EVENTS.append(f"end-{ep}-raise-{type(error).__name__}")


def main() -> None:
    corpus = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))
    workspace = Path.cwd()
    install_seams(workspace)
    sys.path.insert(0, str(workspace))
    import hermes_intelligence.routes.vextrum as vextrum

    streams: dict[str, list] = {}
    for scenario in corpus["scenarios"]:
        STATE.clear()
        for table in ("discovery_runs", "sources", "source_buckets",
                      "question_source_matrix", "organizations"):
            STATE[table] = _decode(scenario.get(table, []))
        if not STATE["organizations"]:
            STATE["organizations"] = [{"id": "org-1", "name": "Hermes",
                                       "vextrum_access": True, "is_internal": True}]
        EVENTS.clear()
        for call in scenario["calls"]:
            run_call(vextrum, call)
        streams[scenario["id"]] = list(EVENTS)
    sys.stdout.write(json.dumps(streams, ensure_ascii=True, default=str))


if __name__ == "__main__":
    main()
