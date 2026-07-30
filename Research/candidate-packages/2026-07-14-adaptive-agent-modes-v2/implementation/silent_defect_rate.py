#!/usr/bin/env python3
"""silent_defect_rate — how often the environment would have said "done" when it wasn't.

This is the number worth publishing, and nobody reports it. Score says how good
the work was. `silent_defect_rate` says something different and more useful:
**of the defects a held-out oracle can see, how many did the arm's OWN evidence
miss while it believed it was finished?**

A defect only counts as SILENT if the arm claimed done. An arm whose suite went
red and said so has no silent defect — it has an honest failure, which is the
whole point of the environment. That distinction is the metric.

  visible signal  what the arm itself had to go on:
                    * a gated (loop) arm -> its pre-submit gate's own re-run;
                    * any other arm -> the repository's public tests.
  held-out oracle the fixture's hidden grader, which the agent never sees.

  silent_defect_rate = |oracle dimensions failing| / |oracle dimensions|,
                       counted ONLY when the visible signal said done.

Counting DIMENSIONS rather than weighting them is deliberate: the score already
carries the weights, and the question here is "how many distinct things did it
miss", not "how badly".

An arm with a high score and a high silent_defect_rate is the dangerous one: it
looks finished and is not. That is exactly the failure the check-admission
machinery claims to prevent, so this is the metric that can falsify the claim.
If the loop arm's silent_defect_rate is not below a well-configured vanilla's,
check admission is theatre and we say so.

Usage:  python silent_defect_rate.py --campaign <campaign.json> [--output <path>]
        python silent_defect_rate.py --run-record <run-record.json>
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent


def visible_verdict(record: dict[str, Any]) -> tuple[bool, str]:
    """Did the arm's OWN evidence say it was done? Returns (claimed_done, source).

    Read per-arm rather than uniformly: a loop arm's visible signal is the gate's
    harness-executed suite, while a bare arm has nothing but the repo's tests.
    Judging a bare arm by a gate it never ran would flatter it; judging a loop arm
    by the public tests would ignore the very thing being measured.
    """
    gate = record.get("pre_submit_gate")
    if gate:
        return bool(gate.get("verdict") == "PASS" and gate.get("completion_allowed")), "pre-submit-gate"
    public = record.get("public_tests") or {}
    return bool(public.get("passed")), "public-tests"


def compute(record: dict[str, Any]) -> dict[str, Any]:
    oracle = record.get("grader") or {}
    dimensions = oracle.get("checks") or []
    claimed_done, source = visible_verdict(record)

    if not dimensions:
        # A missing or crashed oracle is NOT a clean run. Returning 0.0 here would
        # silently report the best possible result for the worst possible evidence.
        return {
            "run_id": record.get("run_id"), "arm": record.get("arm"), "case_id": record.get("case_id"),
            "claimed_done": claimed_done, "visible_signal": source,
            "oracle_dimensions": 0, "silent_defects": [], "silent_defect_rate": None,
            "oracle_score": oracle.get("score"),
            "note": "the held-out oracle reported no dimensions: silent_defect_rate is UNDEFINED, not zero",
        }

    failing = [str(row.get("id")) for row in dimensions if not row.get("passed")]
    silent = failing if claimed_done else []
    return {
        "run_id": record.get("run_id"), "arm": record.get("arm"), "case_id": record.get("case_id"),
        "claimed_done": claimed_done, "visible_signal": source,
        "oracle_dimensions": len(dimensions),
        "oracle_failing": failing,
        "silent_defects": silent,
        "silent_defect_rate": round(len(silent) / len(dimensions), 4),
        "oracle_score": oracle.get("score"),
        "note": ("claimed done while the oracle sees failures: these are silent defects"
                 if silent else
                 "the arm claimed done and the oracle agrees" if claimed_done else
                 "the arm did NOT claim done: its failures are honest, not silent"),
    }


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Per-arm summary. Runs with an undefined rate are excluded from the mean and
    reported separately: averaging over a broken oracle would launder it."""
    by_arm: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_arm.setdefault(str(row.get("arm")), []).append(row)

    arms = {}
    for arm, entries in sorted(by_arm.items()):
        rated = [e for e in entries if e["silent_defect_rate"] is not None]
        undefined = len(entries) - len(rated)
        rates = [e["silent_defect_rate"] for e in rated]
        arms[arm] = {
            "trials": len(entries),
            "undefined_oracle_runs": undefined,
            "claimed_done": sum(1 for e in entries if e["claimed_done"]),
            "claimed_done_with_silent_defects": sum(1 for e in entries if e["silent_defects"]),
            "silent_defect_rate_mean": round(statistics.mean(rates), 4) if rates else None,
            "silent_defect_rate_per_trial": rates,
            "distinct_silent_dimensions": sorted({d for e in entries for d in e["silent_defects"]}),
        }
    return {"schema_version": 1, "arms": arms, "runs": rows,
            "rule": ("a defect is SILENT only when the arm's own evidence said done; an arm that "
                     "reported red has an honest failure, not a silent defect")}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def from_campaign(campaign_path: Path) -> dict[str, Any]:
    campaign = _load(campaign_path)
    repo = campaign_path.resolve()
    for parent in repo.parents:
        if (parent / "Runtime/stable/manifest.json").exists():
            repo = parent
            break
    rows = []
    for entry in campaign.get("runs", []):
        run_id = entry.get("run_id")
        if not run_id:
            continue
        record_path = repo / "Evals/runs" / run_id / "run-record.json"
        if not record_path.is_file():
            rows.append({"run_id": run_id, "arm": entry.get("arm"), "silent_defect_rate": None,
                         "claimed_done": False, "silent_defects": [], "oracle_dimensions": 0,
                         "note": "run-record.json missing: not graded"})
            continue
        record = _load(record_path)
        record.setdefault("run_id", run_id)
        record.setdefault("arm", entry.get("arm"))
        rows.append(compute(record))
    return aggregate(rows)


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--campaign", type=Path)
    group.add_argument("--run-record", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = from_campaign(args.campaign) if args.campaign else compute(_load(args.run_record))
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
