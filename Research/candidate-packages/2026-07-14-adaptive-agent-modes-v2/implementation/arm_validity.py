#!/usr/bin/env python3
"""Does the arm under test actually CONTAIN the mechanism under test?

Written after a campaign was halted at 4 of 28 approved calls. The fixture was
validated (admission 7/7). The metric was validated (10 tests, contract-tested
against real runs). **The ARM was never validated** — its frozen check suite
turned out to be `[symbol-sweep, public-tests]`, holding nothing that could cover
the conventions the task is graded on. The loop arm was vanilla plus a symbol
sweep. The campaign would have "falsified" its own hypothesis for a reason that
had nothing to do with the hypothesis.

THE RULE, WHICH IS OUR OWN, TURNED ON OURSELVES: a check must prove it
discriminates before it counts (`check_admission`). So must an ARM's suite.

The probe is the same one the vacuity gate uses, applied one level up:

    run the arm's frozen suite against the BEFORE state and the AFTER state
      green on both  -> the suite cannot tell the historical bug from the fix.
                        The arm measures NOTHING. Fail closed.
      red on before, green on after -> it discriminates. Admitted.

`after` here is the shipped reference from git history — the same held-out oracle
input the fixture already trusts. No model call, no judgement.

Exit codes: 0 every arm's suite discriminates | 1 at least one arm is vacuous.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import author_role
import harness_checks
from fixture_admission import Gate, local_fixture_dir

# An arm with a loop is claiming to hold checks. A bare control is not, and must
# not be failed for lacking what it is defined not to have.
LOOP_ARMS_MUST_DISCRIMINATE = True


def _variant_workspace(gate: Gate, variant: str, destination: Path) -> Path:
    """Materialize `before` or `after` exactly as the fixture does at grade time."""
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    shutil.copytree(gate.public, destination, dirs_exist_ok=True)
    gate.materialize_into(destination, variant)
    return destination


def _behavioural(suite: dict[str, Any]) -> dict[str, Any]:
    """A symbol sweep asks whether the implementer inspected its consumers. It
    says nothing about whether the suite can see the bug, and it needs the
    scaffold's evidence ledger to run at all — so it is excluded here exactly as
    it is excluded from the loop's own feedback."""
    keep = [c for c in suite.get("checks", []) if c.get("kind") != "symbol-sweep"]
    return dict(suite, checks=keep)


def probe_suite(suite: dict[str, Any], gate: Gate, scratch: Path) -> dict[str, Any]:
    suite = _behavioural(suite)
    if not suite["checks"]:
        return {"verdict": "vacuous", "checks": [],
                "reason": "the arm's frozen suite holds no behavioural check at all: it cannot fail on "
                          "anything the task is graded on, so the arm carries no mechanism"}

    before_ws = _variant_workspace(gate, "before", scratch / "before")
    after_ws = _variant_workspace(gate, "after", scratch / "after")
    before = harness_checks.run_suite(suite, before_ws, baseline_dir=before_ws)
    after = harness_checks.run_suite(suite, after_ws, baseline_dir=before_ws)

    result = {
        "checks": [c.get("id") for c in suite["checks"]],
        "green_on_before": before["green"],
        "green_on_after": after["green"],
        "failing_on_before": list(before["failing_check_ids"]),
        "failing_on_after": list(after["failing_check_ids"]),
    }
    if before["green"]:
        result["verdict"] = "vacuous"
        result["reason"] = ("the arm's suite is GREEN on the pre-change code — the historical bug itself. "
                            "It cannot distinguish the bug from the fix, so it can never make the agent "
                            "do anything, and the arm measures nothing.")
    elif not after["green"]:
        result["verdict"] = "over-constrained"
        result["reason"] = (f"the arm's suite is RED on the SHIPPED reference {result['failing_on_after']}: "
                            "it rejects the real fix, so the loop would chase a target the historical "
                            "engineer never hit. The suite is wrong, not the agent.")
    else:
        result["verdict"] = "discriminates"
        result["reason"] = (f"red on the historical bug {result['failing_on_before']}, green on the shipped "
                            "fix: the suite can see the defect the task is about")
    return result


def validate(fixture_id: str, arms: list[str], scratch: Path) -> dict[str, Any]:
    fixture_dir, contract = local_fixture_dir(fixture_id)
    if contract is None:
        raise SystemExit(f"unknown local fixture: {fixture_id}")
    gate = Gate(fixture_dir)

    # An arm that AUTHORS its checks has no suite yet: there is nothing on disk
    # to probe, because the suite does not exist until a provider call creates
    # it. Probing the compiled shell would report `vacuous` and block a campaign
    # whose whole design is that the shell gets filled at run time.
    authoring = author_role.authoring_policy(fixture_id)

    rows = []
    for arm in arms:
        loop = arm.endswith("-loop")
        if not loop:
            rows.append({"arm": arm, "loop": False, "verdict": "not-applicable",
                         "reason": "a control arm holds no frozen checks by definition; there is nothing "
                                   "to validate, and failing it for that would be nonsense"})
            continue
        if authoring["enabled"]:
            # SAY THE WEAKNESS OUT LOUD. This verdict does not prove the arm
            # discriminates; it records WHERE that proof happens instead:
            #   * check_admission runs every proposed check against this same
            #     pre-change baseline and admits only those that redden on it via
            #     an assertion -- the identical probe, per check, at run time;
            #   * run_ablation_campaign raises AuthoringShortfall and refuses the
            #     trial when nothing behavioural survives, so an arm without the
            #     mechanism produces no number rather than a misattributed one.
            # Those two are load-bearing. They are pinned by tests, at zero calls,
            # because a guarantee nobody tests is a comment.
            rows.append({
                "arm": arm, "loop": True, "verdict": "authored-at-run-time",
                "authoring": authoring,
                "reason": ("the arm's checks are authored by a clean-context subagent during the run, so "
                           "no suite exists to probe now. The vacuity proof moves to check_admission "
                           "(same baseline, same rule, per check) and is enforced by the runner's hard "
                           "stop: no admitted behavioural check means no trial, not a trial without the "
                           "mechanism. This gate does NOT prove discrimination here; it records that the "
                           "proof is deferred to a place that fails closed."),
            })
            continue
        run_dir = scratch / f"arm-{arm}"
        if run_dir.exists():
            shutil.rmtree(run_dir)
        run_dir.mkdir(parents=True)
        workspace = _variant_workspace(gate, "before", run_dir / "workspace")
        harness_dir = fixture_dir / "harness" if (fixture_dir / "harness").is_dir() else None
        from prepare_context import compile_check_suite
        suite = compile_check_suite(workspace, spec_first=False, include_symbol_sweep=False,
                                    harness_dir=harness_dir, script_home=run_dir / "host-checks")
        outcome = probe_suite(suite, gate, run_dir / "probe")
        outcome.update({"arm": arm, "loop": True})
        rows.append(outcome)

    bad = [r for r in rows if r["verdict"] in {"vacuous", "over-constrained"}]
    return {
        "schema_version": 1,
        "fixture": fixture_id,
        "verdict": "PASS" if not bad else "FAIL",
        "arms": rows,
        "rule": ("an arm that claims to hold checks must prove those checks discriminate between the "
                 "historical bug and the shipped fix; otherwise the arm carries no mechanism and any "
                 "result about it is about something else"),
    }


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--arms", required=True, help="comma-separated")
    parser.add_argument("--scratch", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    scratch = args.scratch or (HERE / ".arm-validity-scratch")
    result = validate(args.fixture, [a.strip() for a in args.arms.split(",") if a.strip()], scratch)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    shutil.rmtree(scratch, ignore_errors=True)
    raise SystemExit(0 if result["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
