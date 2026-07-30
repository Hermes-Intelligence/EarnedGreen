#!/usr/bin/env python
"""Prove all five arms can be prepared without exposing hidden graders or calling providers.

Fail-closed admission wiring: a preflight can only PASS when the fixture has a
fresh Fixture Admission Gate record (candidate fixtures) or is one of the
contracted catalog fixtures already covered by a fresh eval-validity PASS.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import arm_validity
from fixture_admission import admission_status, fixture_fingerprint, local_fixture_dir

HERE = Path(__file__).resolve().parent
CANDIDATE = HERE.parent
# CONTEXT arms: what `prepare_adaptive_run` can build. Not the campaign's arms.
ARMS = ["vanilla", "vanilla-configured", "lite", "standard", "critical"]


def design_arms() -> list[str]:
    """The arms the CAMPAIGN runs, from the design that defines them.

    Not `ARMS`. Those are context arms and none of them ends in `-loop`, so
    handing them to arm_validity produced a page of `not-applicable` and a PASS
    that had inspected nothing -- our own vacuity rule, broken by our own gate,
    in the gate written to stop exactly that.
    """
    design = json.loads((HERE / "ablation-design.json").read_text(encoding="utf-8-sig"))
    return [row["id"] for row in design["arms"]]


def repo_root() -> Path:
    for parent in (HERE, *HERE.parents):
        if (parent / "Runtime/stable/manifest.json").exists():
            return parent
    raise RuntimeError("AgenticWorkBestPractices root not found")


def gate_fixture(fixture: str) -> dict:
    """Fail-closed semantic gate lookup for the fixture that would receive spend."""
    repo = repo_root()
    fixture_dir, _ = local_fixture_dir(fixture)
    if fixture_dir is not None:
        status = admission_status(fixture, fixture_dir)
        status["gate"] = "fixture-admission"
        return status
    contracts = json.loads((HERE / "eval-contracts.json").read_text(encoding="utf-8-sig"))
    if any(row["id"] == fixture for row in contracts["fixtures"]):
        validity_path = CANDIDATE / "evidence" / "eval-validity.json"
        if not validity_path.is_file():
            return {"gate": "eval-validity", "admitted": False, "record_path": str(validity_path),
                    "reason": "no eval-validity evidence: run eval_validity.py first"}
        validity = json.loads(validity_path.read_text(encoding="utf-8-sig"))
        if validity.get("verdict") != "PASS":
            return {"gate": "eval-validity", "admitted": False, "record_path": str(validity_path),
                    "reason": "eval-validity verdict is not PASS"}
        fixture_dir = repo / "Evals/fixtures" / fixture
        newest = fixture_fingerprint(fixture_dir)["newest_mtime"] if fixture_dir.is_dir() else 0.0
        if validity_path.stat().st_mtime < newest:
            return {"gate": "eval-validity", "admitted": False, "record_path": str(validity_path),
                    "reason": "eval-validity evidence is stale: fixture files changed after it was generated"}
        return {"gate": "eval-validity", "admitted": True, "record_path": str(validity_path), "reason": None}
    return {"gate": "fixture-admission", "admitted": False, "record_path": None,
            "reason": f"fixture {fixture!r} is neither an admitted candidate fixture nor a contracted catalog fixture"}


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", default="adaptive-contract-evolution-v2")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    admission = gate_fixture(args.fixture)
    rows = []
    if admission["admitted"]:
        with tempfile.TemporaryDirectory(prefix="adaptive-ablation-") as temp_name:
            root = Path(temp_name)
            for arm in ARMS:
                target = root / arm
                completed = subprocess.run(
                    [sys.executable, str(HERE / "prepare_adaptive_run.py"), "--fixture", args.fixture, "--arm", arm, "--output", str(target)],
                    text=True, capture_output=True, encoding="utf-8", errors="replace", timeout=60)
                paths = [path.relative_to(target).as_posix().lower() for path in target.rglob("*")] if target.exists() else []
                hidden = [path for path in paths if "hidden" in path or path.endswith("grade.py")]
                manifest = json.loads((target / "run-manifest.json").read_text(encoding="utf-8")) if (target / "run-manifest.json").exists() else {}
                rows.append({"arm": arm, "prepared": completed.returncode == 0, "hidden_paths": hidden, "provider_calls": manifest.get("provider_calls"), "completion_gate": manifest.get("completion_gate")})
    # Control arms hold no gate BY DEFINITION: the gate is the thing under test.
    # Failing them for lacking it would be nonsense.
    controls = {"vanilla", "vanilla-configured"}
    failures = [row for row in rows if not row["prepared"] or row["hidden_paths"] or row["provider_calls"] != 0
                or (row["arm"] not in controls and not row["completion_gate"])]

    # DOES THE ARM CONTAIN THE MECHANISM UNDER TEST? A campaign was halted at 4 of
    # 28 approved calls because nobody asked: the loop arm's suite was [public-tests]
    # and could not fail on anything the task is graded on. The fixture was
    # validated, the metric was validated, the ARM was not. This closes that.
    arm_check = {"verdict": "SKIPPED", "reason": "no local fixture contract"}
    if admission["admitted"] and local_fixture_dir(args.fixture)[1] is not None:
        try:
            campaign_arms = design_arms()
            arm_check = arm_validity.validate(args.fixture, campaign_arms, Path(tempfile.mkdtemp(prefix="arm-validity-")))
            if not any(row["loop"] for row in arm_check["arms"]):
                arm_check = {"verdict": "FAIL", "arms": arm_check["arms"],
                             "reason": f"no loop arm was inspected (arms: {campaign_arms}): a gate that "
                                       "validates only the arms without the mechanism validates nothing"}
        except Exception as error:  # noqa: BLE001 - a probe that crashes must not silently pass
            arm_check = {"verdict": "FAIL", "reason": f"{type(error).__name__}: {error}"}

    verdict = ("PASS" if admission["admitted"] and rows and not failures
               and arm_check["verdict"] in {"PASS", "SKIPPED"} else "FAIL")
    result = {
        "schema_version": 4,
        "verdict": verdict,
        "fixture": args.fixture,
        "provider_calls": 0,
        "fixture_admission": admission,
        "arm_validity": arm_check,
        "arms": rows,
        "planned_paid_provider_calls_after_approval": 6,
        "full_verifier_counted_separately": True,
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if verdict == "PASS" else 1)


if __name__ == "__main__":
    main()
