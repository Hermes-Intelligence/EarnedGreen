#!/usr/bin/env python3
"""Recording driver for the VextrumDataFlow pipeline-core era fixture.

Stubs psycopg2 ITSELF (not pipeline.db): the workspace's own db seam — and any
reshaping of it an implementation chooses — executes for real, and the two
databases are distinguished at the true seam, the connection DSN. The stub
emulates exactly two contracts, never SQL semantics:

  * the psycopg2 %s paramstyle: a statement whose %s count does not match its
    parameter count raises (the era's real arg-alignment bug reproduces
    mechanically);
  * a tiny canned state machine per KNOWN table (scenario-provided rows,
    keyed writes); an unknown table is a totality finding, not a guess.

Events are semantic, normalized, and value-bearing where the value IS the
behaviour (`ret-materialize-n0` is how "a second run does nothing" becomes
mechanically gradable). Event grammar: kind is everything before the first
":" and contains no colon; `<conn>-<verb>-<surface>[-<outcome>]`.

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

_TS_KEYS = {"as_of_hermes_intelligence", "last_as_of", "materialized_at", "event_timestamp"}


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


def _dispatch(tag: str, sql: str, params) -> list[dict]:
    placeholders = sql.count("%s")
    given = len(params) if params else 0
    if placeholders != given:
        EVENTS.append(f"err-params:{placeholders}vs{given}")
        raise ProgrammingError(f"parameter mismatch: {placeholders} placeholders, {given} params")
    s = " ".join(sql.split()).lower()
    params = list(params or [])

    # Route on the statement's PRIMARY table (INSERT INTO x / UPDATE x / first
    # FROM x) — subqueries legitimately mention other tables (the planner's
    # pending query filters event_records BY steps) and must not hijack routing.
    match = (re.search(r"insert\s+into\s+([a-z0-9_.\"]+)", s)
             or re.search(r"^update\s+([a-z0-9_.\"]+)", s)
             or re.search(r"\bfrom\s+([a-z0-9_.\"]+)", s))
    primary = match.group(1) if match else ""

    if "uds_selection_criteria" in primary:
        EVENTS.append(f"{tag}-q-criteria")
        return [c for c in STATE["criteria"] if params and params[0] == STATE["workspace"]]

    if "materialization_watermark" in primary:
        if s.startswith("select"):
            EVENTS.append(f"{tag}-q-watermark")
            wm = STATE.get("watermark")
            return [{"last_as_of": wm}] if wm is not None else []
        value = _first_datetime(params)
        existed = STATE.get("watermark") is not None
        if s.startswith("update"):
            if existed and value is not None:
                STATE["watermark"] = value
                EVENTS.append(f"{tag}-w-watermark")
                return [{"workspace_id": STATE["workspace"]}] if "returning" in s else []
            return []
        if value is not None:
            STATE["watermark"] = value
        EVENTS.append(f"{tag}-w-watermark")
        return []

    if "uds.events" in primary:
        EVENTS.append(f"{tag}-q-events")
        rows = list(STATE["uds_events"])
        if "as_of_hermes_intelligence >= %s" in sql and params:
            cutoff = params[0]
            rows = [e for e in rows if e["as_of_hermes_intelligence"] >= cutoff]
        return sorted(rows, key=lambda e: e["as_of_hermes_intelligence"])

    if "records_data_operations_steps" in primary or "execution_runs" in primary:
        return _dispatch_exec_tables(tag, primary, s, sql, params)

    if "event_records" in primary:
        if s.startswith("insert"):
            key = (str(params[0]), str(params[1]))
            if key in STATE["record_keys"]:
                EVENTS.append(f"{tag}-w-records-dup")
            else:
                STATE["record_keys"].add(key)
                STATE["event_records"].append({
                    "id": _next("er"), "workspace_id": params[0], "uds_event_id": params[1],
                    "title": params[3] if len(params) > 3 else "", "materialized_at": _next_ts()})
                EVENTS.append(f"{tag}-w-records-new")
            return []
        if "where id = %s" in s:
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
    raise ProgrammingError(f"stub knows no table in: {sql[:120]}")


def _dispatch_exec_tables(tag: str, primary: str, s: str, sql: str, params: list) -> list[dict]:
    if "records_data_operations_steps" in primary:
        if s.startswith("insert"):
            STATE["steps"].append({
                "id": _next("step"), "event_record_id": str(params[0]),
                "component_id": str(params[1]), "workspace_config_hash": str(params[6]),
                "status": "RUNNING", "output_data": None, "completed_at": _next_ts()})
            EVENTS.append(f"{tag}-w-step-new")
            return [{"id": STATE["steps"][-1]["id"]}]
        if s.startswith("update"):
            match = re.search(r"set status = '(\w+)'", s)
            status = match.group(1).upper() if match else "UNKNOWN"
            step_id = str(params[-1])
            for step in STATE["steps"]:
                if step["id"] == step_id:
                    step["status"] = status
                    step["completed_at"] = _next_ts()
                    if status == "SUCCEEDED" and params:
                        step["output_data"] = params[0]
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
        return [{"output_data": r["output_data"], "status": r["status"]} for r in rows]

    if s.startswith("insert"):
        EVENTS.append(f"{tag}-w-run-PLANNED")
        return [{"id": _next("run")}]
    match = re.search(r"set status = '(\w+)'", s)
    status = match.group(1).upper() if match else str(params[0])
    EVENTS.append(f"{tag}-w-run-{status}")
    return []


class _Cursor:
    def __init__(self, tag: str, dict_rows: bool):
        self.tag, self.dict_rows, self.rows = tag, dict_rows, []

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, sql, params=None):
        self.rows = _dispatch(self.tag, sql, params)

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

def load_state(spec: dict, current_hash: str) -> None:
    STATE.clear()
    STATE.update({
        "workspace": spec.get("workspace", "ws-1"),
        "criteria": _load_rows(spec.get("criteria")),
        "watermark": _iso(spec["watermark"]) if spec.get("watermark") else None,
        "uds_events": _load_rows(spec.get("uds_events")),
        "event_records": _load_rows(spec.get("event_records")),
        "steps": [],
        "config": spec.get("config"),
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
            "completed_at": _next_ts()})


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
                      "record_keys": set(), "steps": [], "config": scenario.get("config"),
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
