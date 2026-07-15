#!/usr/bin/env python3
"""Observable context-selection/use telemetry; does not infer private reasoning."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def analyze_run(run: Path, marker_catalog: dict[str, list[str]]) -> dict:
    record = json.loads((run / "run-record.json").read_text(encoding="utf-8-sig"))
    pack_path = run / "workspace/.agentic/context-manifest.json"
    if not pack_path.exists():
        pack_path = run / "workspace/.agentic/context-pack.json"
    events_path = run / "workspace/.agentic/provider-events.jsonl"
    raw_events = events_path.read_text(encoding="utf-8-sig").lower() if events_path.exists() else ""
    selected = []
    if pack_path.exists():
        pack = json.loads(pack_path.read_text(encoding="utf-8-sig"))
        selected = [row["id"] for row in pack.get("modules", pack.get("selected_modules", []))]
    modules = []
    for module_id in selected:
        filename = f".agentic/modules/{module_id}.md"
        opened = filename in raw_events
        markers = marker_catalog.get(module_id, [])
        marker_hits = sorted({marker for marker in markers if marker.lower() in raw_events})
        modules.append({"id": module_id, "selected": True, "opened": opened, "observable_marker_hits": marker_hits, "action_linked": bool(marker_hits), "note": "action_linked is lexical telemetry, not a claim about private reasoning"})
    core_selected = (run / "workspace/.agentic/core.md").is_file()
    core_opened = ".agentic/core.md" in raw_events
    return {"run_id": run.name, "fixture": record["case_id"], "arm": record["arm"], "tokens": record["token_usage"]["total_observed_tokens"], "core":{"selected":core_selected,"opened":core_opened}, "selected_modules": modules, "selected_count": len(selected), "opened_count": sum(row["opened"] for row in modules), "action_linked_count": sum(row["action_linked"] for row in modules), "observable_only": True}


def analyze(run_id: str, marker_catalog: dict[str, list[str]]) -> dict:
    return analyze_run(REPO / "Evals/runs" / run_id, marker_catalog)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", action="append", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    catalog = json.loads((HERE / "router-catalog.json").read_text(encoding="utf-8-sig"))
    markers = {row["id"]: row.get("outcome_markers", []) for row in catalog["modules"]}
    runs = [analyze(run_id, markers) for run_id in args.run_id]
    result = {"schema_version":2,"observable_only":True,"runs":runs,"totals":{"selected":sum(row["selected_count"] for row in runs),"opened":sum(row["opened_count"] for row in runs),"action_linked":sum(row["action_linked_count"] for row in runs)}}
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
