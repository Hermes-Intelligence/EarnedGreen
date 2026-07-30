#!/usr/bin/env python3
"""Derive the hermes-etl fixture's grader predicates from the REAL git diff.

This is the first fixture whose held-out oracle is not hand-written: the
predicates come from diff_oracle's mechanical derivation over the scenario
corpus, with the altformat variant filtering implementation-pinning candidates
— the exact pipeline measured to achieve perfect separation on vextrum.

Two predicate classes land in hidden/derived-predicates.json:

  discriminating  projections that DIFFER between before and after and agree
                  with the altformat variant: the observable consequences of
                  the behaviour change (red on before by construction);
  preserving      `seq` values identical between before and after on guard
                  scenarios: requirement 1 ("default behaviour unchanged") as
                  pinned streams (green on both by construction, red on any
                  deviation a solution introduces).

Every predicate carries its scenario's FAMILY; the grader reports one dimension
per family, so the contract's declared checks stay stable while the predicates
inside them are mechanical. Zero provider calls.
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

FIXTURE = "hermes-etl-skip-v1"
RUNNER_TIMEOUT = 60


def capture_streams(workspace: Path, fixture_dir: Path) -> dict:
    completed = subprocess.run(
        [sys.executable, str(fixture_dir / "hidden/etl_runner.py"), str(fixture_dir / "hidden/scenarios.json")],
        cwd=workspace, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=RUNNER_TIMEOUT)
    if completed.returncode != 0:
        raise RuntimeError(f"etl_runner failed in {workspace}: {completed.stderr[-400:]}")
    return json.loads(completed.stdout)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scratch", type=Path, required=True)
    args = parser.parse_args()

    fixture_dir, contract = local_fixture_dir(FIXTURE)
    if contract is None:
        raise SystemExit(f"fixture {FIXTURE} not found/contracted")
    gate = Gate(fixture_dir)
    families = {row["id"]: row["family"]
                for row in json.loads((fixture_dir / "hidden/scenarios.json").read_text(encoding="utf-8-sig"))["scenarios"]}

    workspaces = {}
    for variant in ("before", "after", "after-altformat"):
        workspaces[variant] = arm_validity._variant_workspace(gate, variant, args.scratch / variant)
    streams = {variant: capture_streams(ws, fixture_dir) for variant, ws in workspaces.items()}

    derived = diff_oracle.derive(streams["before"], streams["after"], [streams["after-altformat"]])
    discriminating = [dict(pred, family=families[pred["input_id"]]) for pred in derived["admitted"]]

    preserving = []
    for input_id, family in families.items():
        b, a = streams["before"].get(input_id), streams["after"].get(input_id)
        if isinstance(b, list) and b == a:
            preserving.append({"id": f"{input_id}::preserve-seq", "input_id": input_id,
                               "projection": "seq", "expected": b, "family": family})

    covered = {pred["family"] for pred in discriminating} | {pred["family"] for pred in preserving}
    missing = sorted(set(families.values()) - covered)
    if missing:
        raise SystemExit(f"derivation left dimension(s) without any predicate: {missing} — "
                         "a dimension with no predicate would pass vacuously; fix the corpus")

    out = {
        "schema_version": 1,
        "source": "mechanically derived from HermesAirflow 37423b0^..37423b0 over hidden/scenarios.json; "
                  "altformat variant filtered implementation-pinning candidates",
        "rejected_format_pinning": derived["rejected_format_pinning"],
        "discriminating": discriminating,
        "preserving": preserving,
    }
    target = fixture_dir / "hidden/derived-predicates.json"
    target.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    by_family: dict[str, int] = {}
    for pred in discriminating + preserving:
        by_family[pred["family"]] = by_family.get(pred["family"], 0) + 1
    print(json.dumps({"discriminating": len(discriminating), "preserving": len(preserving),
                      "rejected_format_pinning": derived["rejected_format_pinning"],
                      "per_family": by_family, "written": str(target)}, indent=2))


if __name__ == "__main__":
    main()
