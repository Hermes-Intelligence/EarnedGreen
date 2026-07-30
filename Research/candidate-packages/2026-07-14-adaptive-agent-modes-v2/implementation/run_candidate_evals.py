#!/usr/bin/env python
"""Run every zero-provider Candidate v2 gate and write a single evidence summary."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Historical INPUT artifacts always live in the package's own evidence directory.
# Only outputs follow --output; deriving inputs from the output dir made the suite
# fail when writing the summary anywhere outside the package.
PACKAGE_EVIDENCE = HERE.parent / "evidence"
BOUNDARY_FIXTURE = "adaptive-contract-evolution-v2"
# v2 stays valid; v3 is the harder successor with real discriminating headroom
# (see mode-boundary-fixture-v3). Both are gated here so the suite validates each.
BOUNDARY_FIXTURE_V3 = "adaptive-contract-evolution-v3"
# v4 is the wide-headroom successor aimed at the demonstrated multi-hop /
# indirect-propagation blind spot (two independent indirect-consumer chains plus
# a re-run state interaction). All three are gated here so the suite validates each.
BOUNDARY_FIXTURE_V4 = "adaptive-contract-evolution-v4"
# The clarity fixture measures the spec-first planning layer: an UNDERSPECIFIED
# task over an existing codebase whose correctness depends on implicit house
# conventions (the DC WIRE class). It is also the current unpaid fixture that
# exercises the canary rule end to end.
BOUNDARY_FIXTURE_CLARITY = "implicit-conventions-v1"
# The scale fixture is the clarity design over a workspace that EXCEEDS
# single-pass comprehension (~57 modules, ~3.9k lines, decoy stubs, misleading
# PLAN.md): the remaining untested axis after four fixtures in a row scored
# 100 under fair semantic grading on single-pass-sized codebases. It is now
# the genuinely unpaid fixture exercising the canary rule.
BOUNDARY_FIXTURE_SCALE = "implicit-conventions-scale-v1"
# The medi-ny fixture is the FIRST history-grounded, proprietary fixture: the real
# NYRx PDL parser rework from HermesAirflow git history (commits 9835c408..a7ed0fd1),
# graded deterministically offline (pdfplumber, zero provider calls). Its workspace
# is materialized from a local Hermes git ref at grade time; nothing proprietary is
# committed. It is a genuinely unpaid fixture exercising the canary rule.
BOUNDARY_FIXTURE_MEDI_NY = "medi-ny-parser-rework-v1"
# Task family #2, and the FIRST non-Python fixture: the real edition-rendering
# rework from VextrumFrontend git history (778c755^..225e1ef). It exists to test
# the LANGUAGE-AGNOSTIC claim that ships in Stable 0.5.0 and has never been
# checked outside Python. Materialized from a local Vextrum git ref at grade
# time; nothing proprietary is committed. Zero npm deps (the jspdf recording stub
# is the fixture's own), zero provider calls.
BOUNDARY_FIXTURE_VEXTRUM = "vextrum-edition-rework-v1"


def run(name: str, command: list[str]) -> dict:
    completed = subprocess.run(command, cwd=HERE, text=True, capture_output=True,
                               encoding="utf-8", errors="replace", timeout=300)
    return {
        "id": name,
        "verdict": "PASS" if completed.returncode == 0 else "FAIL",
        "exit_code": completed.returncode,
        "command": command,
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
    }


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    evidence = output.parent
    evidence.mkdir(parents=True, exist_ok=True)
    campaign_path = evidence / "ablation-campaign.json"
    if campaign_path.exists():
        existing_campaign = json.loads(campaign_path.read_text(encoding="utf-8-sig"))
        if existing_campaign.get("status") in {"approved", "running", "complete", "failed-infrastructure"}:
            # Completed/approved campaign evidence is immutable. Zero-provider
            # lifecycle validation writes a clearly named disposable probe instead.
            campaign_path = evidence / "zero-provider-campaign-lifecycle-probe.json"
    checks = [
        run("candidate-unit-tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_candidate.py", "-v"]),
        # The verification loop is the schema-4 quality mechanism (harness-frozen
        # independent checks iterated to green): its engine, tamper resistance
        # and termination rules are gated here.
        run("verification-loop-tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_verification_loop.py", "-v"]),
        # Earned green: a check is admitted only if it demonstrably discriminates
        # on the pre-change baseline (vacuity gate), and a green result is
        # certified only if every substantive hunk is necessary for some check
        # (necessity probe). Plus stack detection, so a fresh clone works.
        run("earned-green-tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_earned_green.py", "-v"]),
        # The e2e kind boots a real app, drives it, and tears it down -- the answer
        # to unit tests that pass while the product is broken. Deliberately not
        # coupled to Playwright: `command` is whatever drives the app, which is
        # why this is testable with no browser toolchain installed.
        run("e2e-check-tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_e2e_check.py", "-v"]),
        # Check authoring + adversarial review: the subagent that writes the
        # suite is trusted for nothing (vacuity gate decides), and an adversary
        # only "wins" on a mechanically demonstrated divergence, never a claim.
        run("check-authoring-tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_check_authoring.py", "-v"]),
        # Arm validity: does the arm under test actually CONTAIN the mechanism
        # under test? Pins the defect that halted a campaign at 4 of 28 approved
        # calls -- the loop arm's suite was [public-tests] and could not fail on
        # anything the task is graded on. The fixture was validated, the metric
        # was validated, the ARM was not.
        run("arm-validity-tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_arm_validity.py", "-v"]),
        run("author-role-tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_author_role.py", "-v"]),
        # notes_bank is the institutional learning loop: lessons from observed
        # errors, routed forward, with EARNED persistence (measured transfer or
        # retirement). Built after P1 falsification showed agent errors repeat.
        run("notes-bank-tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_notes_bank.py", "-v"]),
        # tiered-loop package: escalation policy (forced triggers + budgeted
        # support), oracle bootstrap (self-hardening suite for work with no
        # answer key), support council (invariants-as-predicates, prose
        # rejected). Every-environment-case battery, responder-injected.
        run("tiered-package-tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_tiered_package.py", "-v"]),
        # diff_oracle derives predicates MECHANICALLY from the behaviour diff of
        # git history — the first mechanism here that measurably discriminated
        # where three generations of mind-derived predicates failed (9/9
        # defective solutions red, both valid implementations green, 0 calls).
        run("diff-oracle-tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_diff_oracle.py", "-v"]),
        # Layer 2 of the oracle stack (relations + constructive mutants) and the
        # typed verdict (coverage manifest): verification for code with NO
        # history, and the end of green claiming dimensions nobody checked.
        run("relation-manifest-tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_relation_and_manifest.py", "-v"]),
        # The portability proof behind 0.6.0: a FOREIGN repo, a few-line capture,
        # and the whole cloned-user path (derive -> pins -> evaluate, guards).
        run("oracle-cli-tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_oracle_cli.py", "-v"]),
        run("commit-miner-tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_commit_miner.py", "-v"]),
        # silent_defect_rate is the headline metric of the check-admission claim:
        # a defect counts as SILENT only when the arm's own evidence said done.
        run("silent-defect-rate-tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_silent_defect_rate.py", "-v"]),
        run("fixture-admission-tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_fixture_admission.py", "-v"]),
        # Spec-first planning layer: clarity classification, spec validation
        # fail-closed cases, ledger-freeze anti-scope-shrink, acceptance re-execution.
        run("spec-first-tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_spec_first.py", "-v"]),
        # Research utilization: claims->rules traceability, decision-time
        # surfacing (the 20x-finding mechanism) and the report-only hygiene loop.
        run("research-utilization-tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_research_utilization.py", "-v"]),
        # Claims->rules traceability gate: structural problems (unknown claims,
        # missing artifacts) FAIL; expired claims WARN; unsupported rules are a
        # reported count, never silently hidden.
        run("claims-rules-validator", [sys.executable, "claims_ledger.py", "--map", "claims-rules-map.json", "--output", str(evidence / "claims-validation.json")]),
        # Vault hygiene: dated report generated, zero broken cross-references in
        # the candidate package itself; repo-level findings are informational.
        run("vault-hygiene", [sys.executable, "vault_hygiene.py", "--output-dir", str(evidence), "--gate-package"]),
        run("eval-validity", [sys.executable, "eval_validity.py", "--output", str(evidence / "eval-validity.json")]),
        # The admission record must be regenerated before any preflight or
        # campaign creation so the spend path sees a fresh fingerprint.
        run("fixture-admission-gate", [sys.executable, "fixture_admission.py", "--fixture", str(HERE / "mode-boundary-fixture"), "--output", str(evidence / f"fixture-admission-{BOUNDARY_FIXTURE}.json")]),
        run("failure-attribution", [sys.executable, "failure_attribution.py", "--input", str(PACKAGE_EVIDENCE / "sentinel-attribution-input.json"), "--output", str(evidence / "sentinel-failure-attribution.json")]),
        run("mode-routing", [sys.executable, "mode_routing_evidence.py", "--output", str(evidence / "mode-routing.json")]),
        run("ablation-preflight", [sys.executable, "ablation_preflight.py", "--fixture", BOUNDARY_FIXTURE, "--output", str(evidence / "ablation-preflight.json")]),
        run("ablation-campaign-zero-call", [sys.executable, "new_ablation_campaign.py", "--fixture", BOUNDARY_FIXTURE, "--output", str(campaign_path)]),
        # The harder v3 fixture: regenerate its admission record, then prove a
        # canary campaign is constructible for it (still zero provider calls).
        run("fixture-admission-gate-v3", [sys.executable, "fixture_admission.py", "--fixture", str(HERE / "mode-boundary-fixture-v3"), "--output", str(evidence / f"fixture-admission-{BOUNDARY_FIXTURE_V3}.json")]),
        run("ablation-campaign-v3-canary", [sys.executable, "new_ablation_campaign.py", "--fixture", BOUNDARY_FIXTURE_V3, "--output", str(evidence / "zero-provider-campaign-v3-canary-probe.json")]),
        # The v4 fixture: regenerate its admission record, then prove a canary
        # campaign is constructible for it (still zero provider calls).
        run("fixture-admission-gate-v4", [sys.executable, "fixture_admission.py", "--fixture", str(HERE / "mode-boundary-fixture-v4"), "--output", str(evidence / f"fixture-admission-{BOUNDARY_FIXTURE_V4}.json")]),
        run("ablation-campaign-v4-canary", [sys.executable, "new_ablation_campaign.py", "--fixture", BOUNDARY_FIXTURE_V4, "--output", str(evidence / "zero-provider-campaign-v4-canary-probe.json")]),
        # v4 semantic re-grade: re-grade the five saved main-stage runs under the
        # SEMANTIC grader + process metrics (zero provider calls). This is the
        # headline dataset that separates OUTCOME (converged at 100) from PROCESS
        # (consumer enumeration, self-attestation gap) and TOKEN COST.
        run("semantic-regrade-v4", [sys.executable, "regrade_main_v4.py"]),
        # The clarity fixture: regenerate its admission record (class-aware
        # convention-anchor coverage), then prove a one-call canary campaign is
        # constructible for it (still zero provider calls, awaiting approval).
        run("fixture-admission-gate-clarity", [sys.executable, "fixture_admission.py", "--fixture", str(HERE / "mode-boundary-fixture-clarity"), "--output", str(evidence / f"fixture-admission-{BOUNDARY_FIXTURE_CLARITY}.json")]),
        run("ablation-campaign-clarity-canary", [sys.executable, "new_ablation_campaign.py", "--fixture", BOUNDARY_FIXTURE_CLARITY, "--output", str(evidence / "zero-provider-campaign-clarity-canary-probe.json")]),
        # The scale fixture: regenerate its admission record (class-aware
        # convention-anchor coverage, contract-declared format-bearing files),
        # then prove a one-call canary campaign with the raised per-call
        # turn/wall budget is constructible (still zero provider calls,
        # awaiting explicit approval).
        run("fixture-admission-gate-scale", [sys.executable, "fixture_admission.py", "--fixture", str(HERE / "mode-boundary-fixture-scale"), "--output", str(evidence / f"fixture-admission-{BOUNDARY_FIXTURE_SCALE}.json")]),
        run("ablation-campaign-scale-canary", [sys.executable, "new_ablation_campaign.py", "--fixture", BOUNDARY_FIXTURE_SCALE, "--output", str(evidence / "zero-provider-campaign-scale-canary-probe.json")]),
        # The medi-ny fixture: regenerate its admission record (class-aware
        # convention anchors + proprietary/hermes-local-copy materialization),
        # then prove a one-call canary campaign is constructible (still zero
        # provider calls, awaiting explicit approval).
        run("fixture-admission-gate-medi-ny", [sys.executable, "fixture_admission.py", "--fixture", str(HERE / "mode-boundary-fixture-medi-ny"), "--output", str(evidence / f"fixture-admission-{BOUNDARY_FIXTURE_MEDI_NY}.json")]),
        run("ablation-campaign-medi-ny-canary", [sys.executable, "new_ablation_campaign.py", "--fixture", BOUNDARY_FIXTURE_MEDI_NY, "--output", str(evidence / "zero-provider-campaign-medi-ny-canary-probe.json")]),
        run("fixture-admission-gate-vextrum", [sys.executable, "fixture_admission.py", "--fixture", str(HERE / "mode-boundary-fixture-vextrum-edition-v1"), "--output", str(evidence / f"fixture-admission-{BOUNDARY_FIXTURE_VEXTRUM}.json")]),
        # silent_defect_rate: how often an arm said "done" while the held-out
        # oracle saw failures. Recomputed from the REAL decisive campaign on every
        # build, so the headline claim stays tied to evidence on disk rather than
        # to a number someone typed into a document once.
        run("silent-defect-rate", [sys.executable, "silent_defect_rate.py", "--campaign", str(PACKAGE_EVIDENCE / "loop-campaign-medi-ny-v4-lean.json"), "--output", str(evidence / "silent-defect-rate-loop-campaign-medi-ny-v4-lean.json")]),
        run("campaign-safety", [sys.executable, "campaign_safety_test.py"]),
        run("capability-activation", [sys.executable, "capability_activation_audit.py", "--output", str(evidence / "capability-activation-audit.json")]),
        run("mode-boundary-fixture", [sys.executable, "mode_boundary_fixture_validity.py", "--output", str(evidence / "mode-boundary-fixture-validity.json")]),
        run("context-telemetry", [
            sys.executable, "context_telemetry.py",
            "--run-id", "20260713-214021509-api-contract-propagation-vanilla-t1",
            "--run-id", "20260713-214155937-api-contract-propagation-core-router-enforcement-t1",
            "--run-id", "20260713-214324036-coordinated-release-change-vanilla-t1",
            "--run-id", "20260713-214545512-coordinated-release-change-core-router-enforcement-t1",
            "--run-id", "20260713-213752603-resumable-batch-session-core-router-enforcement-t1",
            "--run-id", "20260713-214826731-resumable-batch-session-vanilla-t1",
            "--output", str(evidence / "context-telemetry.json"),
        ]),
    ]
    result = {
        "schema_version": 3,
        "verdict": "PASS" if all(row["verdict"] == "PASS" for row in checks) else "FAIL",
        "passed": sum(row["verdict"] == "PASS" for row in checks),
        "failed": sum(row["verdict"] != "PASS" for row in checks),
        "provider_calls": 0,
        "checks": checks,
    }
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
