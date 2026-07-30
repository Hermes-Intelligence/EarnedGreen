#!/usr/bin/env python3
"""Derive the GEN-4 grader predicates for the vextrum-era-v3-gen4 fixture.

Same mechanical pipeline as build_era_oracle.py, with the instrument the era
probe's validity analysis demanded (evidence/gen4-era-validation-*.json):
RELATIONAL predicates — kinds-superset and per-kind count-direction — instead
of exact projections, so partial real work is rewarded and the reference's
rendering choices are never pinned.

Family policy, SET FROM THE MEASURED VALIDATION, not from intention:
  graded (relational)   charts-lines, charts-table, citation-hygiene,
                        block-citations, ordering — each has admitted
                        relational predicates that separate before from the
                        valid lineage
  preserved-behaviour   exact textseq guards, unchanged from gen-3 (exact IS
                        correct for preservation: the unchanged surface must
                        keep saying the same things)
  UNGRADED, NAMED       enum-normalization (wording-only change: no countable
                        observable — the gen-4 boundary, honestly named);
                        sources-section (gen-4 CAN grade it — 2 admitted
                        predicates — but no CONVENTIONS.md/task.md sentence
                        anchors it, so it is not discoverable by the agent and
                        grading it would break the fixture's fairness rule);
                        plus the gen-3 layout dimensions (bars/ratio/fallback/
                        gaps) which admit nothing relational either.
Zero provider calls.
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
from build_era_oracle import GUARD_FAMILY, GUARD_INPUTS, capture
from fixture_admission import Gate, local_fixture_dir

FIXTURE = "vextrum-era-v3-gen4"

FAMILIES: dict[str, list[str]] = {
    "charts-lines": ["vis-trend", "vis-multiline"],
    "charts-table": ["vis-table"],
    "citation-hygiene": ["cite-run"],
    "block-citations": ["block-cites", "block-many"],
    "ordering": ["mixed"],
}
UNGRADED_NAMED = [
    "enum-normalization (no countable observable — gen-4 boundary)",
    "sources-section (gen-4 gradable but unanchored in the discoverable conventions — fairness rule)",
    "charts-bars-layout", "charts-ratio-layout", "charts-fallback-layout", "coverage-gaps-layout",
]


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

    input_family = {i: f for f, inputs in FAMILIES.items() for i in inputs}
    discriminating, dropped_by_policy = [], 0
    for pred in relational["admitted"]:
        family = input_family.get(pred["input_id"])
        if family is None:
            dropped_by_policy += 1
            continue
        discriminating.append(dict(pred, family=family))

    preserving = []
    for input_id in GUARD_INPUTS:
        b, a = streams["before"].get(input_id), streams["after"].get(input_id)
        if isinstance(b, list) and isinstance(a, list):
            tb, ta = diff_oracle.PROJECTIONS["textseq"](b), diff_oracle.PROJECTIONS["textseq"](a)
            if tb == ta:
                preserving.append({"id": f"{input_id}::preserve-textseq", "input_id": input_id,
                                   "projection": "textseq", "expected": tb, "family": GUARD_FAMILY})

    covered = {p["family"] for p in discriminating}
    missing = sorted(set(FAMILIES) - covered)
    if missing or not preserving:
        raise SystemExit(f"derivation gap: families without predicates {missing}; guards={len(preserving)}")

    out = {"schema_version": 1,
           "source": "GEN-4: relational predicates (kinds-superset + count-direction) mechanically derived "
                     "from VextrumFrontend 3c8af98^..225e1ef over hidden/corpus.json; altformat-filtered; "
                     "family policy set from the measured instrument validation (evidence/gen4-era-validation-*)",
           "rejected_by_variant": relational["rejected_by_variant"],
           "dropped_by_family_policy": dropped_by_policy,
           "ungraded_named_dimensions": UNGRADED_NAMED,
           "discriminating": discriminating, "preserving": preserving}
    target = fixture_dir / "hidden/derived-predicates.json"
    target.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    per_family: dict[str, int] = {}
    for pred in discriminating + preserving:
        per_family[pred["family"]] = per_family.get(pred["family"], 0) + 1
    print(json.dumps({"discriminating": len(discriminating), "preserving": len(preserving),
                      "dropped_by_family_policy": dropped_by_policy,
                      "per_family": per_family, "written": str(target)}, indent=2))


if __name__ == "__main__":
    main()
