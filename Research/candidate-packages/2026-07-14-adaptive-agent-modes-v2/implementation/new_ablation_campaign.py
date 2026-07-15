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

from ablation_preflight import gate_fixture
from fixture_admission import local_fixture_dir, scan_paid_history

HERE = Path(__file__).resolve().parent
ARMS = ["vanilla", "mode-1-lean", "mode-2-routed", "mode-3-assured", "full"]
CHEAPEST_ARM = "vanilla"  # rank 0 in ablation-design.json


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
    design = json.loads((HERE / "ablation-design.json").read_text(encoding="utf-8-sig"))
    return design["canary_policy"]


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
    args = parser.parse_args()
    repo = repo_root()

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
    pinned = [HERE / "modes.json", HERE / "router-catalog.json", HERE / "adaptive_router.py", HERE / "objective_compiler.py", HERE / "pre_submit_gate.py", HERE / "eval_validity.py", HERE / "fixture_admission.py"]
    campaign_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-adaptive-mode-ablation"

    if canary_required and canary_evidence is None:
        stage = "canary"
        arms = [CHEAPEST_ARM]
        verifier_runs = []
        total_calls = 1
        scope = "exactly one canary call on the cheapest arm; every further arm needs a separate approval after the canary run-record is validated"
    elif canary_required:
        stage = "main-after-canary"
        arms = [arm for arm in ARMS if arm != CHEAPEST_ARM]
        verifier_runs = [{"run_key":f"screen::{args.fixture}::full-verifier::t1","arm":"full","trial":1,"role":"independent-verifier","depends_on":f"screen::{args.fixture}::full::t1","status":"pending","run_id":None}]
        total_calls = len(arms) + 1
        scope = f"exactly {total_calls} provider calls: {len(arms)} remaining solutions plus one Full verifier, after a validated canary"
    else:
        stage = "main"
        arms = list(ARMS)
        verifier_runs = [{"run_key":f"screen::{args.fixture}::full-verifier::t1","arm":"full","trial":1,"role":"independent-verifier","depends_on":f"screen::{args.fixture}::full::t1","status":"pending","run_id":None}]
        total_calls = len(arms) + 1
        scope = f"exactly {total_calls} provider calls: five solutions plus one Full verifier"

    runs = [{"run_key":f"screen::{args.fixture}::{arm}::t1","arm":arm,"trial":1,"role":"solution","status":"pending","run_id":None} for arm in arms]
    random.Random(campaign_id).shuffle(runs)

    # Per-fixture loop overrides (scale fixtures raise the per-call turn/wall
    # budget so a low score measures prioritization, not truncation). Only the
    # two per-call budgets are overridable; call counts and the kill switch are
    # never fixture-controlled.
    loop = {"max_total_provider_calls":total_calls,"max_calls_per_invocation":total_calls,"max_replacements":0,"max_turns_per_call":18,"max_wall_minutes_per_call":25,"kill_switch":"Evals/local/STOP","automatic_followup":False}
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
        "schema_version":3,
        "campaign_id":campaign_id,
        "status":"awaiting-explicit-approval",
        "stage":stage,
        "provider_calls":0,
        "fixture":args.fixture,
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
