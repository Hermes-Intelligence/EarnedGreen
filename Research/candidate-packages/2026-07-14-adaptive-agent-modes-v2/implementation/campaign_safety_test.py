#!/usr/bin/env python
"""Zero-provider lifecycle checks for the adaptive campaign approval boundary."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Every admitted fixture eventually accumulates live paid history (the clarity
# fixture's one-call canary ran on 2026-07-15), so the canary rule is exercised
# against a synthesized empty runs directory (--runs-dir) instead of depending on
# the mutable live Evals/runs state. The fixture id below only needs a PASSing
# admission gate; its real paid history is deliberately ignored here.
CANARY_FIXTURE = "implicit-conventions-v1"  # admitted candidate fixture; unpaid state synthesized via --runs-dir
CANARY_FIXTURE_DIR = "mode-boundary-fixture-clarity"
HISTORY_FIXTURE = "open-world-record-parser"       # contracted fixture with valid paid history


def run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *args], cwd=HERE, text=True, capture_output=True,
                          encoding="utf-8", errors="replace", timeout=120)


def fake_canary_record(path: Path, *, arm: str = "vanilla", outcome_valid: bool = True, dims: int | None = None) -> None:
    contract = json.loads((HERE / CANARY_FIXTURE_DIR / "fixture-contract.json").read_text(encoding="utf-8-sig"))
    reported = contract["checks"] if dims is None else contract["checks"][:dims]
    checks = [{"id": check, "passed": True, "weight": 10} for check in reported]
    record = {"case_id": CANARY_FIXTURE, "arm": arm, "outcome_valid": outcome_valid,
              "grader": {"passed": False, "score": 60, "checks": checks}}
    path.write_text(json.dumps(record), encoding="utf-8")


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    checks = []
    with tempfile.TemporaryDirectory(prefix="adaptive-campaign-safety-") as temp_name:
        temp = Path(temp_name)

        # --- fixtures without any semantic gate are refused outright ---
        refused = run(["new_ablation_campaign.py", "--fixture", "totally-ungated-fixture", "--output", str(temp / "refused.json")])
        checks.append({"id":"ungated-fixture-refused","passed":refused.returncode != 0 and not (temp / "refused.json").exists()})

        # --- main-stage lifecycle on a fixture with valid paid history ---
        # Design: 5 arms (vanilla, vanilla-configured, vanilla-loop, standard,
        # standard-loop), 3 trials for a verdict, loop arms reserve 3 iteration
        # calls per trial. This fixture declares NO checks of its own, so each
        # loop arm ALSO reserves 1 check-authoring call per trial (author_role):
        #   ceiling = 3 * (1 + 1 + [3+1] + 1 + [3+1]) = 3 * 11 = 33.
        # That +1-per-loop-trial IS the mechanism P1 measures; a ceiling that did
        # not reserve it would strand a trial with its suite unbuilt.
        EXPERIMENT_ARMS = {"vanilla", "vanilla-configured", "vanilla-loop", "standard", "standard-loop",
                           "relation-loop", "oracle-loop"}  # 0.6.0 design: +2 derived-suite loop arms
        campaign_path = temp / "campaign.json"
        created = run(["new_ablation_campaign.py", "--fixture", HISTORY_FIXTURE, "--output", str(campaign_path)])
        campaign = json.loads(campaign_path.read_text(encoding="utf-8-sig"))
        checks.append({"id":"create-zero-call","passed":created.returncode == 0 and campaign["provider_calls"] == 0 and campaign["status"] == "awaiting-explicit-approval" and campaign["stage"] == "main"})
        arms = {row["arm"] for row in campaign["runs"]}
        checks.append({"id":"loop-experiment-arms-multi-trial","passed":arms == EXPERIMENT_ARMS and len(campaign["runs"]) == 21 and campaign["trials"] == 3 and campaign["verdict_eligible"] and campaign["independent_verifier_runs"] == [] and campaign["loop"]["max_total_provider_calls"] == 57 and campaign["loop"]["authoring"]["enabled"]})
        exploratory_path = temp / "exploratory.json"
        exploratory_created = run(["new_ablation_campaign.py", "--fixture", HISTORY_FIXTURE, "--output", str(exploratory_path), "--trials", "1"])
        exploratory = json.loads(exploratory_path.read_text(encoding="utf-8-sig"))
        checks.append({"id":"single-trial-marked-exploratory","passed":exploratory_created.returncode == 0 and not exploratory["verdict_eligible"] and exploratory["trials"] == 1 and exploratory["loop"]["max_total_provider_calls"] == 19})
        unapproved = run(["run_ablation_campaign.py", "--campaign", str(campaign_path), "--max-calls", "1"])
        after = json.loads(campaign_path.read_text(encoding="utf-8-sig"))
        checks.append({"id":"unapproved-run-refused","passed":unapproved.returncode != 0 and after["provider_calls"] == 0})
        wrong = run(["approve_ablation_campaign.py", "--campaign", str(campaign_path), "--approved-by", "test-owner", "--exact-calls", "5"])
        after = json.loads(campaign_path.read_text(encoding="utf-8-sig"))
        checks.append({"id":"wrong-call-count-refused","passed":wrong.returncode != 0 and after["status"] == "awaiting-explicit-approval" and after["provider_calls"] == 0})
        approved = run(["approve_ablation_campaign.py", "--campaign", str(campaign_path), "--approved-by", "test-owner", "--exact-calls", "57"])
        after = json.loads(campaign_path.read_text(encoding="utf-8-sig"))
        checks.append({"id":"approval-does-not-execute","passed":approved.returncode == 0 and after["status"] == "approved" and after["provider_calls"] == 0})
        zero = run(["run_ablation_campaign.py", "--campaign", str(campaign_path), "--max-calls", "0"])
        after = json.loads(campaign_path.read_text(encoding="utf-8-sig"))
        checks.append({"id":"invalid-invocation-ceiling-refused","passed":zero.returncode != 0 and after["provider_calls"] == 0})

        # --- canary rule on a fixture without valid paid history (synthesized) ---
        empty_runs = temp / "no-paid-history-runs"
        empty_runs.mkdir()
        canary_path = temp / "canary.json"
        created = run(["new_ablation_campaign.py", "--fixture", CANARY_FIXTURE, "--output", str(canary_path), "--runs-dir", str(empty_runs)])
        canary = json.loads(canary_path.read_text(encoding="utf-8-sig")) if canary_path.exists() else {}
        checks.append({"id":"canary-forced-for-unpaid-fixture","passed":created.returncode == 0 and canary.get("stage") == "canary" and canary["loop"]["max_total_provider_calls"] == 1 and [row["arm"] for row in canary["runs"]] == ["vanilla"] and canary["independent_verifier_runs"] == []})
        wide = run(["approve_ablation_campaign.py", "--campaign", str(canary_path), "--approved-by", "test-owner", "--exact-calls", "6"])
        checks.append({"id":"canary-wide-approval-refused","passed":wide.returncode != 0 and json.loads(canary_path.read_text(encoding="utf-8-sig"))["status"] == "awaiting-explicit-approval"})
        one = run(["approve_ablation_campaign.py", "--campaign", str(canary_path), "--approved-by", "test-owner", "--exact-calls", "1"])
        checks.append({"id":"canary-single-call-approvable","passed":one.returncode == 0 and json.loads(canary_path.read_text(encoding="utf-8-sig"))["approval"]["exact_calls"] == 1})

        collapsed_record = temp / "collapsed-run-record.json"
        fake_canary_record(collapsed_record, dims=1)
        blocked = run(["new_ablation_campaign.py", "--fixture", CANARY_FIXTURE, "--output", str(temp / "main-blocked.json"), "--canary-record", str(collapsed_record), "--runs-dir", str(empty_runs)])
        checks.append({"id":"main-stage-blocked-on-collapsed-canary","passed":blocked.returncode != 0 and not (temp / "main-blocked.json").exists()})

        valid_record = temp / "valid-run-record.json"
        fake_canary_record(valid_record)
        main_path = temp / "main.json"
        constructed = run(["new_ablation_campaign.py", "--fixture", CANARY_FIXTURE, "--output", str(main_path), "--canary-record", str(valid_record), "--runs-dir", str(empty_runs)])
        main_campaign = json.loads(main_path.read_text(encoding="utf-8-sig")) if main_path.exists() else {}
        # The canary validates the fixture but is NOT a trial: the main stage
        # runs every design arm (including vanilla) for the full trial count.
        checks.append({"id":"main-stage-constructible-after-valid-canary","passed":constructed.returncode == 0 and main_campaign.get("stage") == "main-after-canary" and main_campaign["loop"]["max_total_provider_calls"] == 57 and {row["arm"] for row in main_campaign["runs"]} == EXPERIMENT_ARMS and main_campaign["independent_verifier_runs"] == []})

    result = {"schema_version":3,"verdict":"PASS" if all(row["passed"] for row in checks) else "FAIL","provider_calls":0,"checks":checks}
    print(json.dumps(result,indent=2))
    raise SystemExit(0 if result["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
