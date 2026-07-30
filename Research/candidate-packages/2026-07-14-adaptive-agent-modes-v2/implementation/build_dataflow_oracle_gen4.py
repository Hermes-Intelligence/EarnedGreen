#!/usr/bin/env python3
"""Derive the GEN-4 grader predicates for the vextrum-dataflow-era-v1 fixture.

Relational pipeline as the era's gen-4 builder, with one policy this fixture's
STATE semantics justify: for WRITE / RETURN / ERROR kinds ("-w-" kinds and the
ret-/err-/end- prefixes) a count-direction predicate is UPGRADED to count-equal
when every valid variant matches the after-count exactly — the number of state
writes and the returned totals are semantics, not style. READ kinds stay at
direction (how often an implementation re-checks something is its own choice).
Preservation guards pin exact seq on inputs where before == after.
Zero provider calls.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import arm_validity
import diff_oracle
from fixture_admission import Gate, local_fixture_dir

FIXTURE = os.environ.get("DATAFLOW_FIXTURE", "vextrum-dataflow-era-v2")
DRIVER_TIMEOUT = 300

FAMILIES: dict[str, list[str]] = {
    "uds-routing": ["mat-first"],
    "incremental-materialization": ["mat-second", "mat-dedup", "mat-incremental"],
    "params-contract": ["mat-filters"],
    "resume-reuse": ["exec-resume", "exec-stale-hash"],
    "execution-robustness": ["exec-fail", "exec-skip"],
    "e2e-chain": ["e2e-chain"],
}
GUARD_FAMILY = "preserved-behaviour"
GUARD_INPUTS = ["g-no-criteria", "g-plan-noconfig", "g-plan-nocomponents"]
UNGRADED_NAMED = [
    "planner-pending-selection (lives in SQL the stub serves permissively — fairness of the stub)",
    "uds-filter-pushdown (source/topic/authority WHERE clauses served permissively)",
    "retry-capping (FAILED >= 3 exclusion — same stub permissiveness)",
    "db-connection-management-internals (db.py runs for real but its pooling/caching choices are free)",
]


def _exactish(kind: str) -> bool:
    return "-w-" in kind or kind.startswith(("ret-", "err-", "end-"))


# RERUN SCENARIOS: the reference itself violates the stated convention on the
# watermark boundary — it re-fetches the boundary event (>=) and REPORTS the
# conflicting insert attempt as work (`ret-materialize-n1` after adding zero
# rows), where CONVENTIONS.md demands "how many records it actually added".
# An implementation with strictly-better semantics (>) reports 0 and emits no
# dup at all. Return-value and dup-presence kinds on rerun inputs therefore pin
# a reference QUIRK, not the convention (measured: the third layer of the
# over-constraint class, evidence/dataflow2-replication-observed.json). The
# SEMANTIC anti-reprocessing pin on those inputs is records-NEW counts, which
# any correct implementation satisfies; ret/dup kinds are dropped there.
RERUN_INPUTS = {"mat-second", "mat-dedup", "mat-incremental"}


def _pins_reference_quirk(pred: dict) -> bool:
    if pred["input_id"] not in RERUN_INPUTS:
        return False
    if pred["relation"] == "kinds-superset":
        return False  # rebuilt below with quirk kinds removed
    kind = pred.get("kind", "")
    return kind.startswith("ret-materialize") or kind.endswith("-w-records-dup")


def capture(workspace: Path, fixture_dir: Path) -> dict:
    completed = subprocess.run(
        [sys.executable, str(fixture_dir / "hidden/dataflow_driver.py"),
         str(fixture_dir / "hidden/corpus.json")],
        cwd=workspace, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=DRIVER_TIMEOUT)
    if completed.returncode != 0:
        raise RuntimeError(f"dataflow_driver failed in {workspace}: {completed.stderr[-400:]}")
    return json.loads(completed.stdout)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scratch", type=Path, required=True)
    args = parser.parse_args()
    fixture_dir, contract = local_fixture_dir(FIXTURE)
    if contract is None:
        raise SystemExit(f"fixture {FIXTURE} not found")
    gate = Gate(fixture_dir)
    streams = {}
    for variant, name in [("before", "before"), ("after", "after"), ("after-altformat", "alt")]:
        ws = arm_validity._variant_workspace(gate, variant, args.scratch / name)
        streams[variant] = capture(ws, fixture_dir)

    relational = diff_oracle.derive_relational(
        streams["before"], streams["after"], [streams["after-altformat"]])
    if relational["driver_errors"]:
        raise SystemExit(f"driver errors during derivation: {relational['driver_errors']}")

    counts = diff_oracle._stream_kind_counts  # noqa: SLF001 - same package, shared helper
    input_family = {i: f for f, inputs in FAMILIES.items() for i in inputs}
    discriminating, dropped_by_policy, upgraded = [], 0, 0
    for pred in relational["admitted"]:
        family = input_family.get(pred["input_id"])
        if family is None:
            dropped_by_policy += 1
            continue
        if _pins_reference_quirk(pred):
            dropped_by_policy += 1
            continue
        if pred["relation"] == "kinds-superset" and pred["input_id"] in RERUN_INPUTS:
            trimmed = [k for k in pred["expected"]
                       if not (k.startswith("ret-materialize") or k.endswith("-w-records-dup"))]
            if not trimmed:
                dropped_by_policy += 1
                continue
            pred = dict(pred, expected=trimmed)
        if pred["relation"] == "count-direction" and _exactish(pred["kind"]):
            after_n = counts(streams["after"][pred["input_id"]]).get(pred["kind"], 0)
            if all(counts(v[pred["input_id"]]).get(pred["kind"], 0) == after_n
                   for v in [streams["after-altformat"]]):
                pred = {"id": f"{pred['input_id']}::count-{pred['kind']}-eq{after_n}",
                        "input_id": pred["input_id"], "relation": "count-equal",
                        "kind": pred["kind"], "expected": after_n, "baseline": pred["baseline"]}
                upgraded += 1
        discriminating.append(dict(pred, family=family))

    preserving = []
    for input_id in GUARD_INPUTS:
        b, a = streams["before"].get(input_id), streams["after"].get(input_id)
        if isinstance(b, list) and isinstance(a, list) and b == a:
            preserving.append({"id": f"{input_id}::preserve-seq", "input_id": input_id,
                               "projection": "seq", "expected": b, "family": GUARD_FAMILY})

    covered = {p["family"] for p in discriminating}
    missing = sorted(set(FAMILIES) - covered)
    if missing or len(preserving) != len(GUARD_INPUTS):
        raise SystemExit(f"derivation gap: families without predicates {missing}; "
                         f"guards={len(preserving)}/{len(GUARD_INPUTS)}")

    out = {"schema_version": 1,
           "source": "GEN-4 relational + state-write count-equal, mechanically derived from "
                     "VextrumDataFlow 9570b0b^..081b23d over hidden/corpus.json; altformat-filtered",
           "rejected_by_variant": relational["rejected_by_variant"],
           "dropped_by_family_policy": dropped_by_policy,
           "upgraded_to_count_equal": upgraded,
           "ungraded_named_dimensions": UNGRADED_NAMED,
           "discriminating": discriminating, "preserving": preserving}
    target = fixture_dir / "hidden/derived-predicates.json"
    target.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    per_family: dict[str, int] = {}
    for pred in discriminating + preserving:
        per_family[pred["family"]] = per_family.get(pred["family"], 0) + 1
    print(json.dumps({"discriminating": len(discriminating), "preserving": len(preserving),
                      "upgraded_to_count_equal": upgraded,
                      "dropped_by_family_policy": dropped_by_policy,
                      "per_family": per_family, "written": str(target)}, indent=2))


if __name__ == "__main__":
    main()
