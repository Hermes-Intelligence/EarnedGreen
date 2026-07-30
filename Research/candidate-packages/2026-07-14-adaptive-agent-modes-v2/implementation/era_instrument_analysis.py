#!/usr/bin/env python3
"""INSTRUMENT ANALYSIS of the era grader — exploratory, never a re-grading.

The era probe measured the instrument more than the arms: agents produced real
behavioural work that exact-projection predicates from a single reference graded
as zero. This tool asks the constructive question at zero calls:

    at WHICH abstraction level does a mechanical predicate first separate
    `before` from the valid lineage (after + altformat), and how do the four
    REAL agent solutions fall at each level?

An ABSTRACTION LADDER per family, coarse to exact:
    moved            the stream differs from before at all
    any-gain         at least one event KIND appears that before lacked
    gains-superset   every kind the reference GAINED over before is present
    kindset-superset the solution's kinds are a superset of the reference's
    kindset-equal    exact set equality            (the shipped grader, charts)
    textseq-equal    exact text emission equality  (the shipped grader, text)

HONESTY RAILS: the output is a MAP of where implementations land — it assigns
no scores, changes no shipped grader, and re-grades nothing. Whether an agent
solution is convention-COMPLIANT at a given level is not decidable mechanically
from one reference; the map shows what a DIVERSE valid-variant pool would have
to adjudicate. Findings feed gen-4 instrument design only.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import diff_oracle
from build_era_oracle import FAMILIES, capture
from fixture_admission import local_fixture_dir

K = diff_oracle.PROJECTIONS["kindset"]
T = diff_oracle.PROJECTIONS["textseq"]


def ladder(stream, before, after) -> dict[str, bool]:
    ks, kb, ka = set(K(stream)), set(K(before)), set(K(after))
    return {
        "moved": stream != before,
        "any-gain": bool(ks - kb),
        "gains-superset": (ka - kb) <= ks,
        "kindset-superset": ka <= ks,
        "kindset-equal": ks == ka,
        "textseq-equal": T(stream) == T(after),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scratch", type=Path, required=True,
                        help="directory holding era2/{before,after,alt} materializations")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repo = HERE
    while not (repo / "Runtime/stable/manifest.json").exists():
        repo = repo.parent
    fixture_dir, _ = local_fixture_dir("vextrum-era-v2")

    canary = json.loads((repo / "Evals/experiments/era-canary.json").read_text(encoding="utf-8-sig"))
    probe = json.loads((repo / "Evals/experiments/era-probe.json").read_text(encoding="utf-8-sig"))
    implementations = {
        "after": args.scratch / "era2/after",
        "altformat": args.scratch / "era2/alt",
        "vanilla": repo / "Evals/runs" / canary["runs"][0]["run_id"] / "workspace",
    }
    for row in probe["runs"]:
        implementations[row["arm"]] = repo / "Evals/runs" / row["run_id"] / "workspace"

    before_streams = capture(args.scratch / "era2/before", fixture_dir)
    streams = {name: capture(path, fixture_dir) for name, path in implementations.items()}

    report: dict[str, dict] = {}
    for family, spec in FAMILIES.items():
        rows = {}
        for name, st in streams.items():
            per_level: dict[str, bool] = {}
            for input_id in spec["inputs"]:
                stream = st.get(input_id)
                if not isinstance(stream, list):
                    per_level = {level: False for level in
                                 ("moved", "any-gain", "gains-superset", "kindset-superset",
                                  "kindset-equal", "textseq-equal")}
                    break
                for level, ok in ladder(stream, before_streams[input_id],
                                        capture_after(streams, input_id)).items():
                    per_level[level] = per_level.get(level, True) and ok
            rows[name] = per_level
        # the separating level: coarsest level at which the valid lineage
        # (after + altformat) holds while before, by construction, does not
        separating = None
        for level in ("any-gain", "gains-superset", "kindset-superset", "kindset-equal", "textseq-equal"):
            if rows["after"].get(level) and rows["altformat"].get(level):
                separating = level
                break
        report[family] = {"separating_level_for_valid_lineage": separating, "implementations": rows}

    result = {
        "schema_version": 1,
        "rails": "exploratory instrument analysis; no scores, no re-grading, no shipped-grader change",
        "ladder_order": ["moved", "any-gain", "gains-superset", "kindset-superset", "kindset-equal", "textseq-equal"],
        "families": report,
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    for family, row in report.items():
        print(f"\n{family}  (valid lineage separates at: {row['separating_level_for_valid_lineage']})")
        header = f"{'impl':16s}" + "".join(f"{level:18s}" for level in result["ladder_order"])
        print(header)
        for name, levels in row["implementations"].items():
            print(f"{name:16s}" + "".join(f"{str(levels.get(level)):18s}" for level in result["ladder_order"]))


def capture_after(streams: dict, input_id: str):
    return streams["after"][input_id]


if __name__ == "__main__":
    main()
