#!/usr/bin/env python
"""Create a zero-call, approval-locked adaptive-mode ablation manifest.

Fail-closed spend gating:
- No campaign can be created for a fixture without a fresh semantic gate
  (Fixture Admission Gate for candidate fixtures, eval-validity for the
  contracted catalog fixtures).
- Canary rule: a fixture with NO prior paid run whose run-record shows
  outcome_valid=true gets a first stage of exactly ONE call on the cheapest
  arm. The remaining arms live in a separate main-stage campaign that is only
  constructible from a canary run-record proving outcome_valid=true, at least
  two distinct hidden dimensions and every declared dimension reported.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from datetime import datetime
from pathlib import Path

import author_role
from ablation_preflight import gate_fixture
from fixture_admission import local_fixture_dir, scan_paid_history

HERE = Path(__file__).resolve().parent
CHEAPEST_ARM = "vanilla"  # rank 0 in ablation-design.json


def design() -> dict:
    return json.loads((HERE / "ablation-design.json").read_text(encoding="utf-8-sig"))


def repo_root() -> Path:
    for parent in HERE.parents:
        if (parent / "Runtime/stable/manifest.json").exists():
            return parent
    raise RuntimeError("repository root not found")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def declared_checks(fixture: str) -> list[str] | None:
    _, local_contract = local_fixture_dir(fixture)
    if local_contract is not None:
        return local_contract["checks"]
    contracts = json.loads((HERE / "eval-contracts.json").read_text(encoding="utf-8-sig"))
    for row in contracts["fixtures"]:
        if row["id"] == fixture:
            return row["checks"]
    return None


def canary_policy() -> dict:
    return design()["canary_policy"]


def validate_canary_record(record_path: Path, fixture: str) -> tuple[dict | None, str | None]:
    """Main stage is only constructible from a sane, valid canary run-record."""
    if not record_path.is_file():
        return None, f"canary run-record not found: {record_path}"
    record = json.loads(record_path.read_text(encoding="utf-8-sig"))
    if record.get("case_id") != fixture:
        return None, f"canary run-record is for {record.get('case_id')!r}, not {fixture!r}"
    if record.get("arm") != CHEAPEST_ARM:
        return None, f"canary must be the cheapest arm ({CHEAPEST_ARM}), got {record.get('arm')!r}"
    if not record.get("outcome_valid"):
        return None, "canary run-record has outcome_valid=false"
    grader = record.get("grader") or {}
    reported = [row.get("id") for row in grader.get("checks", [])]
    if len(set(reported)) < 2:
        return None, f"canary grading collapsed: only {len(set(reported))} distinct hidden dimension(s) reported"
    declared = declared_checks(fixture)
    if declared is not None and set(reported) != set(declared):
        return None, f"canary grading is missing declared dimensions: {sorted(set(declared) - set(reported))}"
    return {
        "run_record": str(record_path),
        "arm": record.get("arm"),
        "outcome_valid": True,
        "score": grader.get("score"),
        "distinct_dimensions": len(set(reported)),
        "declared_dimensions": None if declared is None else len(declared),
    }, None


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--provider", choices=["codex","claude"], default="codex")
    parser.add_argument("--provider-settings", type=Path)
    parser.add_argument("--canary-record", type=Path,
                        help="run-record.json of a completed canary; required to construct the main stage for a fixture without prior valid paid history")
    parser.add_argument("--runs-dir", type=Path,
                        help="override the paid-history scan directory (lifecycle tests only; default Evals/runs)")
    parser.add_argument("--trials", type=int, default=None,
                        help="trials per arm for a main stage (default: the design's min_trials_per_arm_for_verdict; fewer marks the campaign exploratory-no-verdict)")
    parser.add_argument("--arms", default=None,
                        help="comma-separated subset of design arm ids for a main stage (budget-constrained campaigns); unknown ids are rejected")
    parser.add_argument("--max-iterations", type=int, default=None,
                        help="override the design's loop iteration ceiling per trial (only downward; budget-constrained campaigns)")
    parser.add_argument("--derived-suites", type=Path,
                        help="JSON {arm: {layer, pins, corpus?}}: these loop arms take a mechanically "
                             "derived frozen suite instead of authoring one - no author calls reserved")
    args = parser.parse_args()
    repo = repo_root()
    plan = design()
    arms_def = plan["arms"]
    trial_policy = plan["trial_policy"]
    loop_policy = plan["loop_arm_policy"]

    admission = gate_fixture(args.fixture)
    if not admission["admitted"]:
        raise SystemExit(f"fixture not admitted for spend ({admission['gate']}): {admission['reason']}")

    history = scan_paid_history(repo, args.fixture, runs_dir=args.runs_dir)
    canary_required = history["valid_paid_runs"] == 0
    canary_evidence = None
    if canary_required and args.canary_record:
        canary_evidence, error = validate_canary_record(args.canary_record, args.fixture)
        if error:
            raise SystemExit(f"main stage not constructible: {error}")

    settings_path = args.provider_settings or repo / "Evals/local/provider-settings.json"
    settings = json.loads(settings_path.read_text(encoding="utf-8-sig"))
    provider = next(row for row in settings["providers"] if row["id"] == args.provider)
    pinned = [HERE / "modes.json", HERE / "router-catalog.json", HERE / "adaptive_router.py", HERE / "objective_compiler.py", HERE / "pre_submit_gate.py", HERE / "harness_checks.py", HERE / "verification_loop.py", HERE / "eval_validity.py", HERE / "fixture_admission.py"]
    campaign_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-adaptive-mode-ablation"

    max_iterations = int(loop_policy["max_iterations_per_trial"])
    if args.max_iterations:
        if args.max_iterations > max_iterations or args.max_iterations < 1:
            raise SystemExit(f"--max-iterations may only lower the design ceiling ({max_iterations})")
        max_iterations = args.max_iterations
        loop_policy = dict(loop_policy, max_iterations_per_trial=max_iterations,
                           override_note="ceiling lowered for budget; only downward overrides are permitted")
    min_trials = int(trial_policy["min_trials_per_arm_for_verdict"])
    if canary_required and canary_evidence is None:
        stage = "canary"
        trials = 1
        stage_arms = [row for row in arms_def if row["id"] == CHEAPEST_ARM]
        scope = "exactly one canary call on the cheapest arm; every further arm needs a separate approval after the canary run-record is validated"
    else:
        # The canary validates the fixture; it is NOT a trial. Main stages run
        # every design arm for the configured trials.
        stage = "main-after-canary" if canary_required else "main"
        trials = args.trials if args.trials else min_trials
        if trials < 1:
            raise SystemExit("--trials must be >= 1")
        stage_arms = list(arms_def)
        if args.arms:
            wanted = [arm.strip() for arm in args.arms.split(",") if arm.strip()]
            known = {row["id"] for row in arms_def}
            unknown = sorted(set(wanted) - known)
            if unknown:
                raise SystemExit(f"unknown arm ids: {unknown}; design arms are {sorted(known)}")
            stage_arms = [row for row in arms_def if row["id"] in wanted]
        scope = None

    # Does the loop have to author its own checks? Decided here, at zero calls,
    # because the answer changes how many calls the campaign must RESERVE, and a
    # ceiling that does not cover the authoring round would strand a trial
    # halfway through with its suite unbuilt.
    authoring = author_role.authoring_policy(args.fixture)
    derived_suites: dict = {}
    if args.derived_suites:
        derived_suites = json.loads(args.derived_suites.read_text(encoding="utf-8-sig"))
        known_arms = {row["id"] for row in arms_def}
        unknown = sorted(set(derived_suites) - known_arms)
        if unknown:
            raise SystemExit(f"--derived-suites names unknown arms: {unknown}")
        for arm_id, spec in derived_suites.items():
            pins = repo / spec["pins"]
            if not pins.is_file():
                raise SystemExit(f"derived suite for {arm_id!r}: pins file not found: {pins}")

    def arm_iteration_ceiling(row: dict) -> int:
        return max_iterations if row.get("loop") else 1

    def arm_call_ceiling(row: dict) -> int:
        # A derived-suite arm never authors: its predicates already exist on disk.
        authors = row.get("loop") and row["id"] not in derived_suites
        author_calls = authoring["max_calls_per_trial"] if authors else 0
        return arm_iteration_ceiling(row) + author_calls

    total_calls = trials * sum(arm_call_ceiling(row) for row in stage_arms)
    verdict_eligible = stage == "canary" or trials >= min_trials
    if scope is None:
        loop_arm_count = sum(1 for row in stage_arms if row.get("loop"))
        authoring_note = (f" and {authoring['max_calls_per_trial']} check-authoring call per trial"
                          if authoring["enabled"] else "")
        scope = (f"at most {total_calls} provider calls: {len(stage_arms)} arms x {trials} trial(s); "
                 f"{loop_arm_count} loop arm(s) reserve {max_iterations} iteration calls per trial"
                 f"{authoring_note} and may use fewer")

    runs = []
    for trial in range(1, trials + 1):
        for row in stage_arms:
            runs.append({
                "run_key": f"screen::{args.fixture}::{row['id']}::t{trial}",
                "arm": row["id"],
                "context_arm": row.get("context_arm", row["id"]),
                "loop": bool(row.get("loop")),
                "max_iterations": arm_iteration_ceiling(row),
                "trial": trial,
                "role": "solution",
                "status": "pending",
                "run_id": None,
                "iterations": [],
            })
    verifier_runs: list[dict] = []
    random.Random(campaign_id).shuffle(runs)

    # Per-fixture loop overrides (scale fixtures raise the per-call turn/wall
    # budget so a low score measures prioritization, not truncation). Only the
    # two per-call budgets are overridable; call counts and the kill switch are
    # never fixture-controlled.
    loop = {"max_total_provider_calls":total_calls,"max_calls_per_invocation":total_calls,"max_replacements":0,"max_turns_per_call":18,"max_wall_minutes_per_call":25,"kill_switch":"Evals/local/STOP","automatic_followup":False,"authoring":authoring,"derived_suites":derived_suites}
    _, local_contract = local_fixture_dir(args.fixture)
    overrides = (local_contract or {}).get("campaign_loop_overrides") or {}
    applied_overrides = {}
    for key in ("max_turns_per_call", "max_wall_minutes_per_call"):
        if key in overrides:
            loop[key] = int(overrides[key])
            applied_overrides[key] = int(overrides[key])
    if applied_overrides and overrides.get("reason"):
        applied_overrides["reason"] = overrides["reason"]
    result = {
        "schema_version":4,
        "campaign_id":campaign_id,
        "status":"awaiting-explicit-approval",
        "stage":stage,
        "provider_calls":0,
        "fixture":args.fixture,
        "trials":trials,
        "trial_policy":trial_policy,
        "loop_arm_policy":loop_policy,
        "verdict_eligible":verdict_eligible,
        "fixture_admission":admission,
        "paid_history":{"valid_paid_runs":history["valid_paid_runs"],"matching_runs":len(history["matching_runs"]),"runs_dir_overridden":args.runs_dir is not None},
        "canary_policy":canary_policy(),
        "canary_evidence":canary_evidence,
        "provider_snapshot":{"generated_at":settings["generated_at"],"expires_at":settings["expires_at"],"distro":settings.get("distro","AgenticBench"),"provider":provider},
        "model_policy":"same resolved provider model and effort across arms",
        "runs":runs,
        "independent_verifier_runs":verifier_runs,
        "loop":loop,
        "loop_overrides":applied_overrides or None,
        "harness_snapshot":[{"path":str(path.relative_to(HERE.parent)).replace('\\','/'),"sha256":sha(path)} for path in pinned],
        "approval":{"approved_at":None,"approved_by":None,"scope":scope}
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"campaign_id":campaign_id,"status":result["status"],"stage":stage,"planned_calls":total_calls,"provider_calls":0},indent=2))


if __name__ == "__main__":
    main()
