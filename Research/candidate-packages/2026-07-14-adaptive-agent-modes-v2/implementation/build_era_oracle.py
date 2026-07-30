#!/usr/bin/env python3
"""Derive the era fixture's grader predicates from the real 4-commit diff.

Same mechanical pipeline as build_etl_oracle.py, with the one addition the era
demands: a PER-FAMILY PROJECTION POLICY. Draw-event sequences carry coordinates
and ordering that are implementation choices — pinning them would fail every
honest reimplementation of a chart (the measured over-constraint class). So:

  chart families      only `kindset` predicates (what KINDS of things were
                      drawn: before renders charts as text, so kindset alone
                      discriminates — and any valid vector implementation
                      agrees on kinds while differing on coordinates)
  text families       only `textseq` predicates (exact emitted text, in order:
                      text content IS the convention surface for citation /
                      enum / section rules; draw events invisible)
  preservation guards `textseq` pinned where before == after (the unchanged
                      surface must keep SAYING the same things; cosmetic
                      redraw of unchanged inputs stays legal)

The policy is a declared, hand-made grader-design choice (like scenario
families in the ETL fixture); every expectation VALUE inside it is mechanical.
Zero provider calls.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import arm_validity
import diff_oracle
from fixture_admission import Gate, local_fixture_dir

FIXTURE = "vextrum-era-v2"
DRIVER_TIMEOUT = 120

# SET FROM THE DATA, not from intention: the probe showed which projections
# survive the altformat filter AND discriminate per input. Inputs whose era
# change lives only in draw-event details (bars/ratio/fallback layout, sources,
# gaps) have NO implementation-agnostic discriminating projection — grading
# them would pin the reference's geometry, the measured over-constraint class.
# They are DROPPED as graded dimensions and NAMED as unverified in the coverage
# manifest instead of silently absorbed. cite-run keeps `count` (the v1
# clean-win projection: separator PRESENCE without identity).
FAMILIES: dict[str, dict] = {
    "charts-lines": {"inputs": ["vis-trend", "vis-multiline"], "projections": {"kindset", "textseq"}},
    "charts-table": {"inputs": ["vis-table"], "projections": {"textseq"}},
    "citation-hygiene": {"inputs": ["cite-run"], "projections": {"count"}},
    "block-citations": {"inputs": ["block-cites", "block-many"], "projections": {"textseq"}},
    "enum-normalization": {"inputs": ["enum-list"], "projections": {"textseq"}},
    "ordering": {"inputs": ["mixed"], "projections": {"kindset", "textseq"}},
}
GUARD_FAMILY = "preserved-behaviour"
GUARD_INPUTS = ["unicode", "bare-url", "long-prose", "legacy", "empty"]
UNGRADED_NAMED = ["charts-bars-layout", "charts-ratio-layout", "charts-fallback-layout",
                  "sources-section-layout", "coverage-gaps-layout"]


def capture(workspace: Path, fixture_dir: Path) -> dict:
    completed = subprocess.run(
        ["node", str(fixture_dir / "hidden/edition_driver.mjs"),
         str(fixture_dir / "hidden/corpus.json"), "src/editionPdf.js"],
        cwd=workspace, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=DRIVER_TIMEOUT)
    if completed.returncode != 0:
        raise RuntimeError(f"edition_driver failed in {workspace}: {completed.stderr[-400:]}")
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

    derived = diff_oracle.derive(streams["before"], streams["after"], [streams["after-altformat"]])
    input_family = {input_id: family for family, spec in FAMILIES.items() for input_id in spec["inputs"]}

    discriminating = []
    dropped_by_policy = 0
    for pred in derived["admitted"]:
        family = input_family.get(pred["input_id"])
        if family is None:
            dropped_by_policy += 1  # guard inputs never yield discriminating dims
            continue
        if pred["projection"] not in FAMILIES[family]["projections"]:
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
        raise SystemExit(f"derivation gap: families without predicates {missing}; guards={len(preserving)} — "
                         "a dimension with no predicate passes vacuously; fix the corpus or the policy")

    out = {"schema_version": 1,
           "source": "mechanically derived from VextrumFrontend 3c8af98^..225e1ef over hidden/corpus.json; "
                     "altformat-filtered; per-family projection policy applied (kindset for charts, textseq for text)",
           "rejected_format_pinning": derived["rejected_format_pinning"],
           "dropped_by_projection_policy": dropped_by_policy,
           "ungraded_named_dimensions": UNGRADED_NAMED,
           "discriminating": discriminating, "preserving": preserving}
    target = fixture_dir / "hidden/derived-predicates.json"
    target.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    per_family: dict[str, int] = {}
    for pred in discriminating + preserving:
        per_family[pred["family"]] = per_family.get(pred["family"], 0) + 1
    print(json.dumps({"discriminating": len(discriminating), "preserving": len(preserving),
                      "dropped_by_projection_policy": dropped_by_policy,
                      "per_family": per_family, "written": str(target)}, indent=2))


if __name__ == "__main__":
    main()
