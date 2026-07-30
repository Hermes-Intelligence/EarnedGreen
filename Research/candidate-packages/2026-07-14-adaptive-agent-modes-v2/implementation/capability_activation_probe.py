#!/usr/bin/env python3
"""Behavioral, zero-provider proof that all adaptive capabilities are executable.

Every capability is proven by DOING, not by declaration:
  lite      -> minimal core + lossless compact ledger
  standard  -> the verification loop drives a real failure to green through
               agent-side fixes, the gate re-runs the suite itself, and a
               tampered suite fails closed
  continuity-> checkpoint/handoff artifacts gate completion
  critical  -> human scope approval and independent verification block until recorded
  telemetry -> observable-only context usage analysis
"""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from context_telemetry import analyze_run
from prepare_context import prepare
from pre_submit_gate import validate
import verification_loop

HERE = Path(__file__).resolve().parent


def dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def evidence_all_verified(ledger: dict, evidence: dict) -> None:
    requirements = {row["id"]: row for row in ledger["requirements"]}
    for row in evidence["requirements"]:
        items = [{"kind": "behavior", "path": "proof.txt"}]
        for kind in requirements[row["requirement_id"]].get("evidence_required", []):
            if kind == "behavior":
                continue
            items.append({"kind": kind, "command": ["python", "-c", "pass"], "exit_code": 0}
                         if kind in {"test", "migration"} else {"kind": kind, "path": "proof.txt"})
        row.update({"status": "verified", "evidence": items})
    evidence["verification_runs"] = [{"command": ["python", "-c", "pass"], "exit_code": 0}]
    evidence["ambiguity_resolutions"] = [
        {"ambiguity_id": row["id"], "resolution": "probe resolution", "authority": "probe owner"}
        for row in ledger.get("ambiguities", [])
    ]
    evidence["completion_claim"] = {"status": "ready", "summary": "probe"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    checks: list[dict] = []
    with tempfile.TemporaryDirectory() as temp_name:
        root = Path(temp_name)

        # --- lite: minimal core + lossless compact ledger --------------------
        lite_ws = root / "lite"
        lite_ws.mkdir()
        task1 = lite_ws / "task.md"
        task1.write_text("- Update the local documentation.\n- Preserve its example.\n", encoding="utf-8")
        prepare(task1, lite_ws, lite_ws / ".agentic", [], "lite")
        lite_ledger = load(lite_ws / ".agentic/objective-ledger.json")
        checks += [
            {"id": "minimal-core", "pass": (lite_ws / ".agentic/core.md").is_file()},
            {"id": "compact-requirement-ledger", "pass": lite_ledger.get("ledger_profile") == "compact" and len(lite_ledger.get("requirements", [])) == 2},
        ]

        # --- standard: the verification loop actually forces work ------------
        std_ws = root / "standard"
        (std_ws / "tests").mkdir(parents=True)
        task2 = std_ws / "task.md"
        task2.write_text("- Create module.py exposing VALUE = 1.\n- Keep the public test green.\n", encoding="utf-8")
        (std_ws / "tests/test_public.py").write_text(
            "import unittest\n\nclass T(unittest.TestCase):\n    def test_value(self):\n"
            "        import module\n        self.assertEqual(1, module.VALUE)\n", encoding="utf-8")
        prepare(task2, std_ws, std_ws / ".agentic", [], "standard")
        suite_path = std_ws / ".agentic/check-suite.json"
        first = verification_loop.step(suite_path, std_ws)
        (std_ws / "module.py").write_text("VALUE = 1\n", encoding="utf-8")  # the "agent" fixes the failure
        second = verification_loop.step(suite_path, std_ws)
        loop_drives_to_green = first["verdict"] == "continue" and second["verdict"] == "green"

        ledger = load(std_ws / ".agentic/objective-ledger.json")
        evidence = load(std_ws / ".agentic/evidence.json")
        # LEAN (4.1): the agent transcribes NO evidence rows - only the
        # consumer inspection the sweep demands. The gate generates the
        # verification evidence from its own suite re-run.
        lean_evidence_shape = evidence.get("evidence_model") == "harness-generated" and "requirements" not in evidence
        evidence["consumer_inspections"] = [{"path": "tests/test_public.py", "note": "asserts VALUE == 1; contract unchanged"}]
        suite = load(suite_path)
        gate_green = validate(ledger, evidence, std_ws, check_suite=suite)
        harness_written = (gate_green.get("evidence_model") == "harness-generated"
                           and bool((gate_green.get("harness_evidence") or {}).get("green")))
        tampered = json.loads(json.dumps(suite))
        tampered["checks"] = [row for row in tampered["checks"] if row["id"] != "public-tests"]
        gate_tampered = validate(ledger, evidence, std_ws, check_suite=tampered)
        # A red suite must FAIL the lean gate even with zero agent claims.
        (std_ws / "module.py").write_text("VALUE = 2\n", encoding="utf-8")
        gate_red = validate(ledger, evidence, std_ws, check_suite=suite)
        (std_ws / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
        checks += [
            {"id": "verification-loop", "pass": loop_drives_to_green and gate_green["verdict"] == "PASS" and gate_tampered["verdict"] == "FAIL"},
            {"id": "harness-evidence", "pass": lean_evidence_shape and harness_written and gate_red["verdict"] == "FAIL"},
            {"id": "pre-submit-gate", "pass": gate_green["verdict"] == "PASS"},
            {"id": "objective-ledger", "pass": bool(ledger.get("requirements"))},
            {"id": "precision-router", "pass": load(std_ws / ".agentic/mode-decision.json")["context_budget"]["max_modules"] >= 1},
        ]

        # focused-verification (lite's classic path): recorded commands are
        # re-executed by the gate.
        lite_ledger2 = load(lite_ws / ".agentic/objective-ledger.json")
        lite_evidence = load(lite_ws / ".agentic/evidence.json")
        (lite_ws / "proof.txt").write_text("behavior proof", encoding="utf-8")
        evidence_all_verified(lite_ledger2, lite_evidence)
        lite_gate = validate(lite_ledger2, lite_evidence, lite_ws)
        checks.append({"id": "focused-verification", "pass": lite_gate["verdict"] == "PASS" and lite_gate["reexecuted_commands"] >= 1})

        # --- continuity conditionals: checkpoint + handoff gate completion ---
        cont_ws = root / "continuity"
        cont_ws.mkdir()
        task3 = cont_ws / "task.md"
        task3.write_text("Continue this multi-session public API implementation with a durable checkpoint and session handoff.", encoding="utf-8")
        prepare(task3, cont_ws, cont_ws / ".agentic", [], None)
        cont_decision = load(cont_ws / ".agentic/mode-decision.json")
        checkpoint = load(cont_ws / ".agentic/checkpoint.json")
        handoff = load(cont_ws / ".agentic/session-handoff.json")
        cont_ledger = load(cont_ws / ".agentic/objective-ledger.json")
        cont_evidence = load(cont_ws / ".agentic/evidence.json")
        # No tests dir here -> the suite has no executable check -> lean falls
        # back to requiring at least one recorded verification command.
        cont_evidence["verification_runs"] = [{"command": ["python", "-c", "pass"], "exit_code": 0}]
        cont_suite = load(cont_ws / ".agentic/check-suite.json")
        blocked = validate(cont_ledger, cont_evidence, cont_ws, check_suite=cont_suite, checkpoint=checkpoint, handoff=handoff)
        checkpoint.update({"status": "ready", "evidence_refs": ["proof.txt"], "next_action": "Run final integration check"})
        handoff.update({"status": "ready", "verified_state": ["requirements evidenced"], "next_action": "Run final integration check"})
        ready = validate(cont_ledger, cont_evidence, cont_ws, check_suite=cont_suite, checkpoint=checkpoint, handoff=handoff)
        continuity_capabilities = {"durable-checkpoints", "session-handoff-state"} <= set(cont_decision["capabilities"])
        checks += [
            {"id": "durable-checkpoints", "pass": continuity_capabilities and checkpoint["required"] and blocked["verdict"] == "FAIL" and ready["verdict"] == "PASS"},
            {"id": "session-handoff-state", "pass": continuity_capabilities and handoff["required"] and ready["verdict"] == "PASS"},
        ]

        # --- critical: human gate + independent verifier block completion ----
        crit_ws = root / "critical"
        crit_ws.mkdir()
        task4 = crit_ws / "task.md"
        task4.write_text("- Preserve behavior of the release step.", encoding="utf-8")
        prepare(task4, crit_ws, crit_ws / ".agentic", [], "critical")
        crit_ledger = load(crit_ws / ".agentic/objective-ledger.json")
        crit_evidence = load(crit_ws / ".agentic/evidence.json")
        crit_evidence["verification_runs"] = [{"command": ["python", "-c", "pass"], "exit_code": 0}]
        crit_suite = load(crit_ws / ".agentic/check-suite.json")
        crit_blocked = validate(crit_ledger, crit_evidence, crit_ws, check_suite=crit_suite)
        crit_evidence["scope_approval"] = {"status": "approved", "approved_by": "owner"}
        crit_evidence["independent_verification"] = {"status": "PASS", "verifier_profile": "adversarial-review"}
        crit_passed = validate(crit_ledger, crit_evidence, crit_ws, check_suite=crit_suite)
        checks += [
            {"id": "human-approval-boundaries", "pass": crit_blocked["verdict"] == "FAIL" and any(row["id"] == "scope-approval" for row in crit_blocked["failures"]) and crit_passed["verdict"] == "PASS"},
            {"id": "independent-verifier", "pass": any(row["id"] == "independent-verification" for row in crit_blocked["failures"])},
            {"id": "bounded-loop", "pass": load(crit_ws / ".agentic/check-suite.json")["config"]["max_iterations"] >= 1},
        ]

        # --- spec-synthesis conditional wiring --------------------------------
        spec_ws = root / "spec"
        spec_ws.mkdir()
        task5 = spec_ws / "task.md"
        task5.write_text("Build a new adapter for the next state like the existing sources across the pipeline.", encoding="utf-8")
        prepare(task5, spec_ws, spec_ws / ".agentic", [], None)
        spec_decision = load(spec_ws / ".agentic/mode-decision.json")
        spec_suite = load(spec_ws / ".agentic/check-suite.json")
        checks.append({"id": "spec-synthesis", "pass": "spec-synthesis" in spec_decision["capabilities"]
                       and (spec_ws / ".agentic/spec.json").is_file()
                       and any(row["id"] == "spec-frozen" for row in spec_suite["checks"])})

        # --- context-usage telemetry ------------------------------------------
        run = root / "telemetry-probe"
        (run / "workspace/.agentic").mkdir(parents=True)
        dump(run / "workspace/.agentic/context-manifest.json", {"modules": [{"id": "change-impact"}]})
        (run / "workspace/.agentic/core.md").write_text("core", encoding="utf-8")
        (run / "workspace/.agentic/provider-events.jsonl").write_text("opened .agentic/core.md and .agentic/modules/change-impact.md; checked call sites", encoding="utf-8")
        dump(run / "run-record.json", {"case_id": "probe", "arm": "standard", "token_usage": {"total_observed_tokens": 0}})
        telemetry = analyze_run(run, {"change-impact": ["call sites"]})
        checks.append({"id": "context-usage-telemetry", "pass": telemetry["core"]["opened"] and telemetry["opened_count"] == 1 and telemetry["action_linked_count"] == 1})

    result = {"schema_version": 2, "verdict": "PASS" if all(row["pass"] for row in checks) else "FAIL", "provider_calls": 0, "checks": checks}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    dump(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
