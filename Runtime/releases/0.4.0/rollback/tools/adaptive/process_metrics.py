#!/usr/bin/env python
"""Process metrics for adaptive-mode ablation runs (zero provider calls).

The v4 semantic re-grade shows the arms converge on the same OUTCOME once format
noise is removed. The interesting signal then lives in the PROCESS: did the
scaffolding actually enumerate every downstream consumer, edit every required
file, and -- the key instrument -- were its "verified" self-attestations
trustworthy?

Given a run directory (containing run-record.json and workspace/.agentic/
impact-map.json) and the fixture's declared `process_ground_truth`, this module
computes, per run:

  * consumer_enumeration_completeness - fraction of ground-truth downstream
    consumers the agent actually LISTED in its impact-map consumers evidence.
  * consumer_edit_completeness - fraction of required files actually edited
    (from run-record changed_files).
  * impact_map_section_completeness - impact-map sections present and marked
    verified.
  * token_cost - observed tokens from the run record.
  * self_attestation_gap - BOOLEAN + detail: did the run mark impact-map
    consumers "verified" while the SEMANTIC grade is < 100 on a consumer
    dimension (claimed done but a consumer output is semantically wrong)? A run
    with no impact-map (e.g. vanilla) reports this as N/A.

Usage:
  python process_metrics.py --run-dir <dir> --fixture <fixture-dir> [--grade <grade.json>] [--output <json>]
  python process_metrics.py --run-dir <a> --run-dir <b> ... --fixture <fixture-dir> --combined <json>
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None


def load_contract(fixture_dir: Path) -> dict[str, Any]:
    contract = _load_json(fixture_dir / "fixture-contract.json")
    if contract is None:
        raise SystemExit(f"no fixture-contract.json under {fixture_dir}")
    return contract


def find_impact_map(run_dir: Path) -> dict[str, Any] | None:
    for candidate in (run_dir / "workspace/.agentic/impact-map.json",
                      run_dir / ".agentic/impact-map.json",
                      run_dir / "artifacts/returned-workspace/.agentic/impact-map.json"):
        data = _load_json(candidate)
        if data is not None:
            return data
    return None


_SRC_PATH = re.compile(r"src/[\w/]+\.py")


def _enumerated_consumer_paths(impact_map: dict[str, Any]) -> set[str]:
    """Collect every src/*.py path listed under the impact-map consumers section."""
    consumers = ((impact_map.get("sections") or {}).get("consumers") or {})
    paths: set[str] = set()
    for item in consumers.get("evidence", []) or []:
        if isinstance(item, dict):
            explicit = item.get("path")
            if isinstance(explicit, str):
                paths.update(_SRC_PATH.findall(explicit))
            # also catch paths mentioned inside an observation/command string
            for value in item.values():
                if isinstance(value, str):
                    paths.update(_SRC_PATH.findall(value))
    return {p.replace("\\", "/") for p in paths}


def _section_completeness(impact_map: dict[str, Any]) -> dict[str, Any]:
    sections = impact_map.get("sections") or {}
    present = sorted(sections)
    verified = sorted(name for name, body in sections.items()
                      if isinstance(body, dict) and body.get("status") == "verified")
    completeness = round(len(verified) / len(present), 4) if present else None
    return {"sections_present": present, "sections_verified": verified,
            "completeness": completeness}


def _consumer_dimension_status(semantic_grade: dict[str, Any] | None,
                               consumer_dims: list[str]) -> dict[str, bool]:
    if not semantic_grade:
        return {}
    by_id = {row.get("id"): bool(row.get("passed")) for row in semantic_grade.get("checks", [])}
    return {dim: by_id.get(dim, False) for dim in consumer_dims if dim in by_id}


def compute_run_metrics(run_dir: Path, contract: dict[str, Any],
                        semantic_grade: dict[str, Any] | None = None) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    record = _load_json(run_dir / "run-record.json") or {}
    ground = contract.get("process_ground_truth") or {}
    gt_consumers = {p.replace("\\", "/") for p in ground.get("consumers", [])}
    required_edits = {p.replace("\\", "/") for p in ground.get("required_edits", [])}
    consumer_dims = list(ground.get("consumer_dimensions", []))

    impact_map = find_impact_map(run_dir)
    has_impact_map = impact_map is not None

    # consumer enumeration completeness
    if has_impact_map and gt_consumers:
        enumerated = _enumerated_consumer_paths(impact_map)
        hit = sorted(gt_consumers & enumerated)
        missed = sorted(gt_consumers - enumerated)
        enum_completeness = round(len(hit) / len(gt_consumers), 4)
    else:
        enumerated, hit, missed, enum_completeness = set(), [], sorted(gt_consumers), None

    # consumer edit completeness (from changed_files)
    changed = {str(p).replace("\\", "/") for p in record.get("changed_files", [])}
    if required_edits:
        edited = sorted(required_edits & changed)
        unedited = sorted(required_edits - changed)
        edit_completeness = round(len(edited) / len(required_edits), 4)
    else:
        edited, unedited, edit_completeness = [], [], None

    # impact-map section completeness
    sections = _section_completeness(impact_map) if has_impact_map else {
        "sections_present": [], "sections_verified": [], "completeness": None}

    # self-attestation gap
    consumers_section = ((impact_map or {}).get("sections") or {}).get("consumers") or {}
    consumers_verified = consumers_section.get("status") == "verified"
    dim_status = _consumer_dimension_status(semantic_grade, consumer_dims)
    if not has_impact_map:
        gap: bool | None = None
        gap_detail = "N/A: run has no impact-map (no self-attestation to check, e.g. vanilla)"
    elif semantic_grade is None:
        gap = None
        gap_detail = "unknown: no semantic grade supplied; cannot compare claim to outcome"
    else:
        failed_consumer_dims = sorted(dim for dim, ok in dim_status.items() if not ok)
        if consumers_verified and failed_consumer_dims:
            gap = True
            gap_detail = (f"impact-map marked consumers 'verified' but the semantic grade FAILS "
                          f"consumer dimensions {failed_consumer_dims}: the 'verified' claim is not trustworthy")
        elif consumers_verified:
            gap = False
            gap_detail = ("impact-map marked consumers 'verified' and the semantic grade passes every "
                          "consumer dimension: the self-attestation is trustworthy on this run")
        else:
            gap = False
            gap_detail = ("impact-map did not mark consumers 'verified'; no over-claim to reconcile")

    return {
        "run_id": run_dir.name,
        "arm": record.get("arm"),
        "has_impact_map": has_impact_map,
        "token_cost": record.get("tokens"),
        "original_exact_score": (record.get("grader") or {}).get("score"),
        "semantic_score": (semantic_grade or {}).get("score"),
        "consumer_enumeration_completeness": enum_completeness,
        "consumer_enumeration": {"ground_truth": sorted(gt_consumers), "enumerated": sorted(enumerated),
                                 "hit": hit, "missed": missed},
        "consumer_edit_completeness": edit_completeness,
        "consumer_edits": {"required": sorted(required_edits), "edited": edited, "unedited": unedited},
        "impact_map_section_completeness": sections,
        "self_attestation_gap": gap,
        "self_attestation_detail": gap_detail,
        "consumer_dimension_status": dim_status,
    }


def combine(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "kind": "process-metrics-comparison",
        "provider_calls": 0,
        "runs": rows,
        "summary": [
            {
                "arm": r["arm"],
                "run_id": r["run_id"],
                "token_cost": r["token_cost"],
                "original_exact_score": r["original_exact_score"],
                "semantic_score": r["semantic_score"],
                "consumer_enum_completeness": r["consumer_enumeration_completeness"],
                "consumer_edit_completeness": r["consumer_edit_completeness"],
                "self_attestation_gap": r["self_attestation_gap"],
            }
            for r in rows
        ],
    }


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, action="append", required=True, help="run directory (repeatable)")
    parser.add_argument("--fixture", type=Path, required=True, help="fixture directory with fixture-contract.json")
    parser.add_argument("--grade", type=Path, action="append", default=[],
                        help="semantic grade JSON for the matching --run-dir (repeatable, positional to --run-dir)")
    parser.add_argument("--output", type=Path, help="per-run output (only valid with a single --run-dir)")
    parser.add_argument("--combined", type=Path, help="combined comparison output for multiple --run-dir")
    args = parser.parse_args()
    contract = load_contract(args.fixture)
    rows = []
    for index, run_dir in enumerate(args.run_dir):
        grade = None
        if index < len(args.grade):
            grade = _load_json(args.grade[index])
        rows.append(compute_run_metrics(run_dir, contract, grade))
    if args.output and len(rows) == 1:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(rows[0], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    combined = combine(rows)
    if args.combined:
        args.combined.parent.mkdir(parents=True, exist_ok=True)
        args.combined.write_text(json.dumps(combined, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(combined if len(rows) > 1 else rows[0], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
