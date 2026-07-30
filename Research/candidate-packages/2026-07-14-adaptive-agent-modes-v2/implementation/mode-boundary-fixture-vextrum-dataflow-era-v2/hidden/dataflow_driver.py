#!/usr/bin/env python3
"""Recording driver for the VextrumDataFlow pipeline-core era fixture (v2).

Stubs psycopg2 ITSELF (not pipeline.db): the workspace's own db seam — and any
reshaping of it an implementation chooses — executes for real, and the two
databases are distinguished at the true seam, the connection DSN.

V2 REPAIRS THE MEASURED v1 INSTRUMENT DEFECT (the over-constraint class one
layer down — evidence/dataflow-replication-observed.json): v1 served rows in
the REFERENCE'S column aliases and read INSERT parameters positionally, so any
different-but-valid alias or column order crashed. v2 behaves like a database:

  * SELECT rows are PROJECTED onto the query's own column list (aliases,
    table prefixes and ::casts resolved; `SELECT *` serves canonical rows);
  * RETURNING clauses are projected the same way;
  * INSERT parameters are mapped BY COLUMN NAME from the statement's column
    list, never by position;
  * an unknown column or an unmappable insert is a NAMED totality finding
    (err-unknown-column / err-unmappable-insert), exactly like an unknown
    table — a real database would error there too.

The stub still emulates exactly two contracts, never SQL semantics: the
psycopg2 %s paramstyle, and a canned per-table state machine. Events are
semantic, normalized and value-bearing (`ret-materialize-n0` is how "a second
run does nothing" stays mechanically gradable). Event grammar: kind is
everything before the first ":" and contains no colon.

Usage: python dataflow_driver.py <corpus.json> ; run from the WORKSPACE root.
Prints {scenario_id: [event, ...]} as one JSON line. Zero network, zero disk
writes, deterministic by construction.
"""
from __future__ import annotations

import json
import os
import re
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

EVENTS: list[str] = []
STATE: dict = {}
_COUNTERS = {"er": 0, "run": 0, "step": 0, "ts": 0}

_TS_KEYS = {"as_of_hermes_intelligence", "last_as_of", "materialized_at", "event_timestamp",
            "updated_at", "completed_at", "created_at"}


def _iso(value):
    if isinstance(value, str) and re.match(r"^\d{4}-\d{2}-\d{2}T", value):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value


def _load_rows(rows):
    out = []
    for row in rows or []:
        out.append({k: (_iso(v) if k in _TS_KEYS else v) for k, v in row.items()})
    return out


def _next(counter: str) -> str:
    _COUNTERS[counter] += 1
    return f"{counter}-{_COUNTERS[counter]}"


def _next_ts() -> datetime:
    _COUNTERS["ts"] += 1
    return datetime(2026, 7, 1, 12, 0, _COUNTERS["ts"], tzinfo=timezone.utc)


# --- the psycopg2 stub -------------------------------------------------------------

class ProgrammingError(Exception):
    pass


def _first_datetime(params):
    for p in params or []:
        if isinstance(p, datetime):
            return p
    return None


def _token(expr: str) -> str:
    """`ds.source_type::text` -> `source_type`; strips alias prefix, cast, quotes."""
    return expr.strip().split("::")[0].split(".")[-1].strip('"').strip().lower()


def _select_items(clause: str) -> list[tuple[str, str]]:
    """Parse a column list into (output_name, source_token) pairs."""
    items = []
    for raw in clause.split(","):
        raw = raw.strip()
        if not raw:
            continue
        alias_match = re.search(r"(?i)\s+as\s+([a-z0-9_\"]+)\s*$", raw)
        if alias_match:
            items.append((alias_match.group(1).strip('"').lower(), _token(raw[:alias_match.start()])))
        else:
            items.append((_token(raw), _token(raw)))
    return items


def _project(rows: list[dict], s: str) -> list[dict]:
    """Serve each row under the QUERY'S requested names — like a database would."""
    match = re.match(r"select\s+(?:distinct\s+)?(.*?)\s+from\s", s)
    if not match:
        return rows
    clause = match.group(1).strip()
    if clause == "*" or clause.endswith(".*"):
        return rows
    spec = _select_items(clause)
    projected = []
    for row in rows:
        out = {}
        for name, token in spec:
            if token in row:
                out[name] = row[token]
            elif name in row:
                out[name] = row[name]
            elif token in ("1", "count(*)", "now()"):
                out[name] = 1
            else:
                EVENTS.append(f"err-unknown-column:{token}")
                raise ProgrammingError(f"column {token!r} does not exist (see SCHEMA.md)")
        projected.append(out)
    return projected


def _project_returning(rows: list[dict], s: str) -> list[dict]:
    match = re.search(r"\breturning\s+(.+)$", s)
    if not match:
        return rows
    spec = _select_items(match.group(1).strip())
    projected = []
    for row in rows:
        out = {}
        for name, token in spec:
            if token in row:
                out[name] = row[token]
            elif name in row:
                out[name] = row[name]
            else:
                EVENTS.append(f"err-unknown-column:{token}")
                raise ProgrammingError(f"RETURNING column {token!r} does not exist")
        projected.append(out)
    return projected


def _paren_group(s: str, start: int) -> tuple[str, int]:
    """Return the contents of the parenthesized group opening at s[start] == '('."""
    depth, i = 0, start
    while i < len(s):
        if s[i] == "(":
            depth += 1
        elif s[i] == ")":
            depth -= 1
            if depth == 0:
                return s[start + 1:i], i
        i += 1
    raise ValueError("unbalanced parentheses")


def _split_depth(clause: str) -> list[str]:
    """Split on commas at parenthesis depth 0 (so now(), ARRAY[...] stay whole)."""
    parts, depth, current = [], 0, []
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
    return [p.strip() for p in parts if p.strip()]


def _insert_map(s: str, params: list) -> dict:
    """Map INSERT parameters BY COLUMN NAME from the statement's column list.

    Only %s placeholders consume parameters; literals ('PLANNED', now()) are
    kept as literals. An insert whose columns cannot be mapped (INSERT..SELECT,
    missing column list) is a named totality finding — the stub cannot know
    which value lands where, and guessing would grade noise."""
    try:
        head = re.match(r"insert\s+into\s+[a-z0-9_.\"]+\s*", s)
        columns_raw, end = _paren_group(s, s.index("(", head.end()))
        values_at = re.compile(r"\bvalues\s*\(").search(s, end)
        values_raw, _ = _paren_group(s, s.index("(", values_at.start()))
    except (AttributeError, ValueError):
        EVENTS.append("err-unmappable-insert")
        raise ProgrammingError("insert without a mappable (columns) VALUES (...) shape") from None
    columns = [_token(c) for c in _split_depth(columns_raw)]
    value_exprs = _split_depth(values_raw)
    if len(columns) != len(value_exprs):
        EVENTS.append("err-unmappable-insert")
        raise ProgrammingError("insert column/value count mismatch")
    mapped, param_index = {}, 0
    for column, expr in zip(columns, value_exprs):
        if "%s" in expr:
            mapped[column] = params[param_index]
            param_index += 1
        else:
            mapped[column] = expr.strip("'")
    return mapped


def _route(tag: str, s: str, sql: str, params) -> list[dict]:
    match = (re.search(r"insert\s+into\s+([a-z0-9_.\"]+)", s)
             or re.search(r"^update\s+([a-z0-9_.\"]+)", s)
             or re.search(r"\bfrom\s+([a-z0-9_.\"]+)", s))
    primary = match.group(1) if match else ""

    if "uds_selection_criteria" in primary:
        EVENTS.append(f"{tag}-q-criteria")
        return [dict(c) for c in STATE["criteria"]
                if params and params[0] == STATE["workspace"]]

    if "materialization_watermark" in primary:
        if s.startswith("select"):
            EVENTS.append(f"{tag}-q-watermark")
            wm = STATE.get("watermark")
            if wm is None:
                return []
            return [{"workspace_id": STATE["workspace"], "last_as_of": wm, "updated_at": wm}]
        value = _first_datetime(params)
        existed = STATE.get("watermark") is not None
        if s.startswith("update"):
            if existed and value is not None:
                STATE["watermark"] = value
                EVENTS.append(f"{tag}-w-watermark")
                STATE["_rowcount"] = 1
                return [{"workspace_id": STATE["workspace"], "last_as_of": value,
                         "updated_at": value}]
            STATE["_rowcount"] = 0
            return []
        if value is not None:
            STATE["watermark"] = value
        EVENTS.append(f"{tag}-w-watermark")
        return [{"workspace_id": STATE["workspace"], "last_as_of": STATE.get("watermark"),
                 "updated_at": STATE.get("watermark")}]

    if "uds.events" in primary or primary == "events":
        EVENTS.append(f"{tag}-q-events")
        rows = [dict(e) for e in STATE["uds_events"]]
        # honour the query's own watermark comparison: >= or > (both are valid
        # semantics — pinning the reference's operator was the v2.2 lesson),
        # with the cutoff taken from the CORRECT parameter position
        comparison = re.search(r"as_of_hermes_intelligence\s*(>=|>)\s*%s", sql)
        if comparison and params:
            cutoff = params[sql[:comparison.start()].count("%s")]
            if comparison.group(1) == ">=":
                rows = [e for e in rows if e["as_of_hermes_intelligence"] >= cutoff]
            else:
                rows = [e for e in rows if e["as_of_hermes_intelligence"] > cutoff]
        return sorted(rows, key=lambda e: e["as_of_hermes_intelligence"])

    if "records_data_operations_steps" in primary or "execution_runs" in primary:
        return _dispatch_exec_tables(tag, primary, s, sql, params)

    if "event_records" in primary:
        if s.startswith("insert"):
            values = _insert_map(s, params)
            key = (str(values.get("workspace_id")), str(values.get("uds_event_id")))
            if None in key or "None" in key:
                EVENTS.append("err-unmappable-insert")
                raise ProgrammingError("event_records insert names no workspace_id/uds_event_id")
            if key in STATE["record_keys"]:
                EVENTS.append(f"{tag}-w-records-dup")
                STATE["_rowcount"] = 0
                return []  # ON CONFLICT DO NOTHING: no row inserted, RETURNING yields nothing
            STATE["record_keys"].add(key)
            record = {"id": _next("er"), "materialized_at": _next_ts()}
            record.update({k: v for k, v in values.items() if k not in record})
            STATE["event_records"].append(record)
            EVENTS.append(f"{tag}-w-records-new")
            STATE["_rowcount"] = 1
            return [dict(record)]  # a database returns the inserted row to RETURNING
        if re.search(r"where\s+([a-z_]+\.)?id\s*=\s*%s", s):
            EVENTS.append(f"{tag}-q-record")
            return [dict(r) for r in STATE["event_records"] if str(r["id"]) == str(params[0])]
        EVENTS.append(f"{tag}-q-records-pending")
        rows = sorted(STATE["event_records"], key=lambda r: r["materialized_at"], reverse=True)
        return [dict(r) for r in rows]

    if "data_operations_configurations" in primary:
        EVENTS.append(f"{tag}-q-config")
        cfg = STATE.get("config")
        return [dict(cfg)] if cfg else []

    if "data_operations_components" in primary:
        EVENTS.append(f"{tag}-q-components")
        return [dict(c) for c in STATE.get("components", [])]

    if "data_operations_edges" in primary:
        EVENTS.append(f"{tag}-q-edges")
        return [dict(e) for e in STATE.get("edges", [])]

    if "client_config_" in primary or "client_ontology_" in primary or "operating_specs" in primary:
        EVENTS.append(f"{tag}-q-cfg")
        return [{"id": "cfg-row", "version": 1}]

    EVENTS.append("err-unknown-table")
    raise ProgrammingError(f"stub knows no table in: {sql[:120]} (see SCHEMA.md)")


def _dispatch(tag: str, sql: str, params) -> list[dict]:
    placeholders = sql.count("%s")
    given = len(params) if params else 0
    if placeholders != given:
        EVENTS.append(f"err-params:{placeholders}vs{given}")
        raise ProgrammingError(f"parameter mismatch: {placeholders} placeholders, {given} params")
    s = " ".join(sql.split()).lower()
    params = list(params or [])
    STATE.pop("_rowcount", None)
    rows = _route(tag, s, sql, params)
    if s.startswith("select"):
        STATE["_last_rowcount"] = len(rows)
        return _project(rows, s)
    STATE["_last_rowcount"] = STATE.pop("_rowcount", len(rows) if rows else 1)
    if "returning" in s:
        return _project_returning(rows, s)
    return []  # a write without RETURNING yields no rows, exactly like psycopg2


def _dispatch_exec_tables(tag: str, primary: str, s: str, sql: str, params: list) -> list[dict]:
    if "records_data_operations_steps" in primary:
        if s.startswith("insert"):
            values = _insert_map(s, params)
            STATE["steps"].append({
                "id": _next("step"),
                "event_record_id": str(values.get("event_record_id")),
                "component_id": str(values.get("component_id")),
                "execution_run_id": str(values.get("execution_run_id")),
                "component_type": values.get("component_type"),
                "component_version": values.get("component_version"),
                "config_version": values.get("config_version"),
                "workspace_config_hash": str(values.get("workspace_config_hash")),
                "status": values.get("status", "RUNNING"),
                "output_data": values.get("output_data"), "result_code": None,
                "completed_at": _next_ts()})
            EVENTS.append(f"{tag}-w-step-new")
            return [dict(STATE["steps"][-1])]
        if s.startswith("update"):
            # map %s params to column names in statement order (SET a = %s ... WHERE id = %s)
            named = {}
            for column, value in zip(re.findall(r"([a-z_]+)\s*=\s*%s", s), params):
                named.setdefault(column, value)
            literal = re.search(r"status\s*=\s*'(\w+)'", s)
            status = (literal.group(1) if literal else str(named.get("status", "UNKNOWN"))).upper()
            step_id = str(named.get("id", params[-1] if params else ""))
            for step in STATE["steps"]:
                if step["id"] == step_id:
                    step["status"] = status
                    step["completed_at"] = _next_ts()
                    if "output_data" in named:
                        step["output_data"] = named["output_data"]
                    if "result_code" in named:
                        step["result_code"] = named["result_code"]
            EVENTS.append(f"{tag}-w-step-{status}")
            return []
        EVENTS.append(f"{tag}-q-steps")
        statuses = set(re.findall(r"'([A-Z_]+)'", sql))
        record_id, comp_id, cfg_hash = str(params[0]), str(params[1]), str(params[2])
        rows = [s2 for s2 in STATE["steps"]
                if s2["event_record_id"] == record_id and s2["component_id"] == comp_id
                and s2["workspace_config_hash"] == cfg_hash
                and (not statuses or s2["status"] in statuses)]
        rows = sorted(rows, key=lambda r: r["completed_at"], reverse=True)
        return [dict(r) for r in rows]

    if s.startswith("insert"):
        EVENTS.append(f"{tag}-w-run-PLANNED")
        values = _insert_map(s, params)
        run = {"id": _next("run"), "status": values.get("status", "PLANNED")}
        run.update({k: v for k, v in values.items() if k not in run})
        return [run]
    named = {}
    for column, value in zip(re.findall(r"([a-z_]+)\s*=\s*%s", s), params):
        named.setdefault(column, value)
    literal = re.search(r"status\s*=\s*'(\w+)'", s)
    status = (literal.group(1) if literal else str(named.get("status", params[0] if params else "UNKNOWN"))).upper()
    EVENTS.append(f"{tag}-w-run-{status}")
    return []


class _Cursor:
    def __init__(self, tag: str, dict_rows: bool):
        self.tag, self.dict_rows, self.rows = tag, dict_rows, []
        self.rowcount = -1

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, sql, params=None):
        self.rows = _dispatch(self.tag, sql, params)
        self.rowcount = STATE.get("_last_rowcount", -1)

    def fetchall(self):
        return [dict(r) for r in self.rows]

    def fetchone(self):
        if not self.rows:
            return None
        row = self.rows[0]
        return dict(row) if self.dict_rows else tuple(row.values())


class _Connection:
    def __init__(self, dsn: str):
        self.tag = "uds" if "uds" in dsn.lower() else "vex"
        self.autocommit = False
        self.closed = 0

    def cursor(self, cursor_factory=None):
        return _Cursor(self.tag, dict_rows=cursor_factory is not None)


def install_psycopg2() -> None:
    stub = types.ModuleType("psycopg2")
    extras = types.ModuleType("psycopg2.extras")
    extras.RealDictCursor = object()
    stub.connect = lambda dsn: _Connection(str(dsn))
    stub.extras = extras
    stub.ProgrammingError = ProgrammingError
    sys.modules["psycopg2"] = stub
    sys.modules["psycopg2.extras"] = extras


# --- deterministic test components -------------------------------------------------

def register_components(base_module) -> None:
    class Enrich(base_module.Component):
        component_type = "enrich"

        def process(self, event_record, prior_results, step_id):
            return {"e": str(event_record.get("title", "")).lower()}

    class Volatile(base_module.Component):
        component_type = "volatile"

        def process(self, event_record, prior_results, step_id):
            if "poison" in str(event_record.get("title", "")):
                raise RuntimeError("volatile component rejected a poison record")
            return {"v": 1}

    class Filterer(base_module.Component):
        component_type = "filterer"

        def should_skip(self, event_record, prior_results):
            return "irrelevant" in str(event_record.get("title", ""))

        def process(self, event_record, prior_results, step_id):
            return {"f": 1}

    class Publish(base_module.Component):
        component_type = "publish"

        def process(self, event_record, prior_results, step_id):
            return {"p": sorted(str(k) for k in prior_results)}

    for cls in (Enrich, Volatile, Filterer, Publish):
        base_module.register(cls)


# --- scenario runner ---------------------------------------------------------------

def _canonical_event(row: dict) -> dict:
    """Serve events under their SOURCE column names (uds.events e JOIN
    uds.data_sources ds) so alias projection can satisfy any spelling."""
    out = dict(row)
    out.setdefault("source_type", row.get("data_source_type"))
    out.setdefault("source_name", row.get("data_source_name"))
    out.setdefault("data_source_id", "ds-1")
    return out


def load_state(spec: dict, current_hash: str) -> None:
    workspace = spec.get("workspace", "ws-1")
    STATE.clear()
    STATE.update({
        "workspace": workspace,
        "criteria": [dict(c, workspace_id=workspace) for c in _load_rows(spec.get("criteria"))],
        "watermark": _iso(spec["watermark"]) if spec.get("watermark") else None,
        "uds_events": [_canonical_event(e) for e in _load_rows(spec.get("uds_events"))],
        "event_records": _load_rows(spec.get("event_records")),
        "steps": [],
        "config": dict(spec["config"], workspace_id=workspace) if spec.get("config") else None,
        "components": spec.get("components", []),
        "edges": spec.get("edges", []),
    })
    STATE["record_keys"] = {(str(r["workspace_id"]), str(r["uds_event_id"]))
                            for r in STATE["event_records"]}
    for step in spec.get("steps", []) or []:
        cfg_hash = step["workspace_config_hash"]
        cfg_hash = current_hash if cfg_hash == "@current" else cfg_hash
        STATE["steps"].append({
            "id": _next("step"), "event_record_id": str(step["event_record_id"]),
            "component_id": str(step["component_id"]), "workspace_config_hash": cfg_hash,
            "status": step["status"], "output_data": step.get("output_data"),
            "execution_run_id": "run-0", "component_type": None, "component_version": None,
            "config_version": None, "result_code": None, "completed_at": _next_ts()})


def main() -> None:
    corpus_path = Path(sys.argv[1])
    os.environ.setdefault("DATABASE_URL", "stub://vextrum")
    os.environ.setdefault("UDS_DATABASE_URL", "stub://uds")
    install_psycopg2()
    sys.path.insert(0, str(Path.cwd()))

    import pipeline.components.base as base
    import pipeline.config_hash as config_hash
    import pipeline.executor as executor
    import pipeline.materializer as materializer
    import pipeline.planner as planner
    register_components(base)

    corpus = json.loads(corpus_path.read_text(encoding="utf-8-sig"))
    streams: dict[str, list] = {}
    for scenario in corpus["scenarios"]:
        for key in _COUNTERS:
            _COUNTERS[key] = 0
        STATE.clear()
        STATE.update({"workspace": scenario.get("workspace", "ws-1"), "criteria": [],
                      "watermark": None, "uds_events": [], "event_records": [],
                      "record_keys": set(), "steps": [],
                      "config": dict(scenario["config"], workspace_id=scenario.get("workspace", "ws-1"))
                                if scenario.get("config") else None,
                      "components": scenario.get("components", []),
                      "edges": scenario.get("edges", [])})
        EVENTS.clear()
        try:
            current_hash = config_hash.compute(STATE["workspace"])
        except Exception:  # noqa: BLE001 - a broken hash surface is itself an observable
            current_hash = "hash-error"
        load_state(scenario, current_hash)
        EVENTS.clear()

        plan = None
        for action in scenario["actions"]:
            try:
                if action == "materialize":
                    count = materializer.materialize_workspace(STATE["workspace"])
                    EVENTS.append(f"ret-materialize-n{count}")
                    EVENTS.append("end-materialize-ok")
                elif action == "plan":
                    plan = planner.plan_workspace(STATE["workspace"])
                    EVENTS.append("ret-plan-none" if plan is None
                                  else f"ret-plan-n{len(plan['event_record_ids'])}")
                    EVENTS.append("end-plan-ok")
                elif action == "execute":
                    if plan is None:
                        EVENTS.append("ret-exec-noplan")
                        continue
                    stats = executor.execute_run(plan)
                    for key in sorted(stats):
                        EVENTS.append(f"ret-exec-{key}-n{stats[key]}")
                    EVENTS.append("end-execute-ok")
                else:
                    raise ValueError(f"unknown action {action!r}")
            except Exception as error:  # noqa: BLE001 - the ending IS the observable
                EVENTS.append(f"end-{action}-raise-{type(error).__name__}")
        streams[scenario["id"]] = list(EVENTS)

    sys.stdout.write(json.dumps(streams, ensure_ascii=True, default=str))


if __name__ == "__main__":
    main()
