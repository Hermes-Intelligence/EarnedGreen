#!/usr/bin/env python3
"""EXPLORATORY validation of the gen-4 relational instrument on era material.

A NEW experiment on OLD material: derives relational predicates (kinds-superset,
count-direction) from the era's before/after/altformat, then evaluates the four
REAL probe implementations against them. Registered predictions:
evidence/gen4-instrument-predictions.json (written before this ran).

HONESTY RAILS: no scores, no re-grading of the probe, no shipped-grader change.
The output is per-predicate verdict maps; verdict-grade arm comparisons need
fresh runs under a fixed instrument.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import arm_validity
import diff_oracle
from build_era_oracle import FAMILIES, GUARD_INPUTS, capture
from fixture_admission import Gate, local_fixture_dir


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repo = HERE
    while not (repo / "Runtime/stable/manifest.json").exists():
        repo = repo.parent
    fixture_dir, contract = local_fixture_dir("vextrum-era-v2")
    if contract is None:
        raise SystemExit("fixture vextrum-era-v2 not found")
    gate = Gate(fixture_dir)

    lineage = {}
    for variant, name in [("before", "before"), ("after", "after"), ("after-altformat", "alt")]:
        ws = arm_validity._variant_workspace(gate, variant, args.scratch / name)
        lineage[variant] = capture(ws, fixture_dir)

    derived = diff_oracle.derive_relational(
        lineage["before"], lineage["after"], [lineage["after-altformat"]])

    canary = json.loads((repo / "Evals/experiments/era-canary.json").read_text(encoding="utf-8-sig"))
    probe = json.loads((repo / "Evals/experiments/era-probe.json").read_text(encoding="utf-8-sig"))
    agents = {"vanilla": repo / "Evals/runs" / canary["runs"][0]["run_id"] / "workspace"}
    for row in probe["runs"]:
        agents[row["arm"]] = repo / "Evals/runs" / row["run_id"] / "workspace"

    input_family = {i: f for f, spec in FAMILIES.items() for i in spec["inputs"]}
    verdicts = {"before": diff_oracle.evaluate(derived["admitted"], lineage["before"]),
                "after": diff_oracle.evaluate(derived["admitted"], lineage["after"]),
                "altformat": diff_oracle.evaluate(derived["admitted"], lineage["after-altformat"])}
    for name, ws in agents.items():
        verdicts[name] = diff_oracle.evaluate(derived["admitted"], capture(ws, fixture_dir))

    per_predicate = {}
    for pred in derived["admitted"]:
        row = {name: next(c["verdict"] for c in v["checks"] if c["id"] == pred["id"])
               for name, v in verdicts.items()}
        per_predicate[pred["id"]] = {
            "relation": pred["relation"],
            "family": input_family.get(pred["input_id"], "guard-or-unmapped"),
            "verdicts": row}

    guard_leaks = [p["id"] for p in derived["admitted"] if p["input_id"] in GUARD_INPUTS]
    result = {
        "schema_version": 1,
        "rails": "exploratory; new experiment on old material; no scores; no re-grading",
        "admitted": len(derived["admitted"]),
        "rejected_by_variant": derived["rejected_by_variant"],
        "driver_errors": derived["driver_errors"],
        "guard_input_predicates": guard_leaks,
        "per_predicate": per_predicate,
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    print(f"admitted={len(derived['admitted'])} rejected_by_variant={derived['rejected_by_variant']} "
          f"guard_leaks={guard_leaks}")
    names = list(verdicts)
    print(f"{'predicate':46s}" + "".join(f"{n:20s}" for n in names))
    for pid, row in per_predicate.items():
        print(f"{pid:46s}" + "".join(f"{row['verdicts'][n]:20s}" for n in names))


if __name__ == "__main__":
    main()
