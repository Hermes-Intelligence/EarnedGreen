#!/usr/bin/env python3
"""Derive the GEN-4 grader predicates for the portal-insights-era-v1 fixture.

Same relational pipeline as the dataflow builder. Policy notes:
  * every payload-fact kind (bucket order, aggregate values, edge tuples,
    response keys, endings, http statuses) is DATA-DETERMINED — count-equal
    applies wherever the altformat variant agrees exactly;
  * db-read kinds (q-*) are implementation pacing — direction only;
  * guards pin exact seq on the preserved-endpoints scenario (before == after).
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

FIXTURE = "portal-insights-era-v1"
DRIVER_TIMEOUT = 300

FAMILIES: dict[str, list[str]] = {
    "buckets-canonical": ["buckets-rich"],
    "bucket-aggregations": ["buckets-agg"],
    "matrix-enrichment": ["matrix-enriched"],
    "coverage-tolerance": ["coverage-dict", "coverage-stringified"],
    "serialization-safety": ["sources-serialization"],
    "empty-vs-404": ["empty-shapes", "missing-run"],
}
GUARD_FAMILY = "preserved-behaviour"
GUARD_INPUTS = ["g-preserved"]
UNGRADED_NAMED = [
    "sources-filtering-and-sorting (multi-select IN, tier casts, sort whitelist — wide SQL grammar; corpus never exercises it: the family-2 lesson applied by construction)",
    "follow-up-new-only (same reason)",
    "filtered-page-count-consistency (same reason)",
    "keyset-cursor-pagination (helpers exist in the module; slice uses page numbers)",
]


def _exactish(kind: str) -> bool:
    return not kind.startswith("q-")


def capture(workspace: Path, fixture_dir: Path) -> dict:
    completed = subprocess.run(
        [sys.executable, str(fixture_dir / "hidden/portal_driver.py"),
         str(fixture_dir / "hidden/corpus.json")],
        cwd=workspace, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=DRIVER_TIMEOUT)
    if completed.returncode != 0:
        raise RuntimeError(f"portal_driver failed in {workspace}: {completed.stderr[-400:]}")
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
           "source": "GEN-4 relational + payload-fact count-equal, mechanically derived from "
                     "HermesPortal 7c77cb0^..1e762e5 over hidden/corpus.json; altformat-filtered",
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
