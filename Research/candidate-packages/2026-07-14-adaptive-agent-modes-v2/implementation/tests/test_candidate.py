from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
IMPL = HERE.parent
sys.path.insert(0, str(IMPL))

from adaptive_router import route
from failure_attribution import attribute
from harness_checks import harness_freeze_sha256
from objective_compiler import compile_ledger
from prepare_context import prepare
from pre_submit_gate import validate
from resolve_capability_profile import resolve


def green_suite() -> dict:
    suite = {"schema_version": 1, "config": {},
             "checks": [{"id": "ok", "kind": "acceptance", "authored_by": "harness",
                         "command": [sys.executable, "-c", "raise SystemExit(0)"]}]}
    suite["harness_freeze_sha256"] = harness_freeze_sha256(suite)
    return suite


class CandidateTests(unittest.TestCase):
    def test_all_routing_cases(self) -> None:
        cases = json.loads((HERE / "mode-cases.json").read_text(encoding="utf-8"))["cases"]
        for case in cases:
            with self.subTest(case=case["id"]):
                result = route(case["task"], case.get("changed_paths"))
                selected = {row["id"] for row in result["selected_modules"]}
                self.assertEqual(case["expected_mode"], result["mode"])
                self.assertTrue(set(case["required"]) <= selected, (case["id"], selected))
                self.assertFalse(set(case["forbidden"]) & selected, (case["id"], selected))
                self.assertTrue(set(case.get("expected_capabilities", [])) <= set(result["capabilities"]),
                                (case["id"], result["capabilities"]))

    def test_forced_mode_is_explicit_and_does_not_hide_policy(self) -> None:
        result = route("Change a public API response schema.", forced_mode="lite")
        self.assertEqual("lite", result["mode"])
        self.assertEqual("standard", result["policy_selected_mode"])
        self.assertEqual("benchmark-forced", result["selection_source"])

    def test_compiled_scope_escalates_lite_to_standard_before_mutation(self) -> None:
        # The router sees a mechanical one-liner (lite), but the compiled ledger
        # exceeds the trivial boundary: prepare must escalate to standard
        # before any mutation. The only scope-based escalation left.
        task_text = ("Mechanical typo cleanup pass.\n"
                     "Do not modify task.md. Preserve the example output. Keep headings intact.\n"
                     "Update the changelog line. Fix the broken link. Retain the licence header.\n")
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            task = root / "task.md"
            task.write_text(task_text, encoding="utf-8")
            router_only = route(task_text)
            self.assertEqual("lite", router_only["mode"])
            result = prepare(task, root, root / ".agentic", [], None)
            decision = json.loads((root / ".agentic" / "mode-decision.json").read_text(encoding="utf-8"))
            self.assertEqual("standard", result["mode"])
            self.assertEqual("adaptive-policy-escalated", decision["selection_source"])

    def test_objective_compiler_flags_real_ambiguities(self) -> None:
        ledger = compile_ledger("- Reject a non-empty string.\n- Document that legacy email is retained.")
        self.assertEqual(2, len(ledger["requirements"]))
        descriptions = " ".join(row["description"] for row in ledger["ambiguities"])
        self.assertIn("whitespace-only", descriptions)
        self.assertIn("semantic", descriptions)

    def test_objective_compiler_captures_normative_prose_outside_bullets(self) -> None:
        ledger = compile_ledger("# Task: implement the feature\n\n- Return a result.\n\nDo not modify `task.md` or existing tests.")
        statements = " ".join(row["statement"].lower() for row in ledger["requirements"])
        self.assertIn("implement the feature", statements)
        self.assertIn("do not modify", statements)
        self.assertEqual(0, ledger["coverage"]["uncaptured_normative_statement_count"])

    def test_gate_fails_closed_then_passes_complete_evidence(self) -> None:
        ledger = compile_ledger("- Return the value and test invalid input.")
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            (root / "proof.txt").write_text("proof", encoding="utf-8")
            evidence = {
                "mode": "standard",
                "requirements": [],
                "ambiguity_resolutions": [],
                "verification_runs": [],
                "completion_claim": {"status": "in_progress"},
            }
            self.assertEqual("FAIL", validate(ledger, evidence, root)["verdict"])
            req = ledger["requirements"][0]
            ok = [sys.executable, "-c", "raise SystemExit(0)"]
            evidence.update({
                "requirements": [{
                    "requirement_id": req["id"],
                    "status": "verified",
                    "evidence": [
                        {"kind": "behavior", "path": "proof.txt"},
                        {"kind": "test", "command": ok, "exit_code": 0},
                    ],
                }],
                "verification_runs": [{"command": ok, "exit_code": 0}],
                "completion_claim": {"status": "ready"},
            })
            self.assertEqual("PASS", validate(ledger, evidence, root)["verdict"])

    def test_gate_resolves_linux_python_alias_on_windows_host(self) -> None:
        ledger = compile_ledger("- Verify portable execution.")
        req = ledger["requirements"][0]
        command = "python3 -c \"raise SystemExit(0)\""
        evidence = {
            "mode": "standard",
            "requirements": [{"requirement_id":req["id"],"status":"verified","evidence":[{"kind":"test","command":command,"exit_code":0}]}],
            "ambiguity_resolutions": [],
            "verification_runs": [{"command":command,"exit_code":0}],
            "completion_claim": {"status":"ready"},
        }
        with tempfile.TemporaryDirectory() as temp_name, patch("pre_submit_gate.shutil.which", return_value=None):
            self.assertEqual("PASS", validate(ledger, evidence, Path(temp_name))["verdict"])

    def test_gate_ignores_broken_python3_alias_on_windows(self) -> None:
        ledger = compile_ledger("- Verify the Windows execution boundary.")
        req = ledger["requirements"][0]
        command = "python3 -c \"raise SystemExit(0)\""
        evidence = {"mode":"standard","requirements":[{"requirement_id":req["id"],"status":"verified","evidence":[{"kind":"test","command":command,"exit_code":0}]}],"ambiguity_resolutions":[],"verification_runs":[{"command":command,"exit_code":0}],"completion_claim":{"status":"ready"}}
        with tempfile.TemporaryDirectory() as temp_name, patch("pre_submit_gate.sys.platform", "win32"), patch("pre_submit_gate.shutil.which", return_value="C:/broken/python3.cmd"):
            self.assertEqual("PASS", validate(ledger, evidence, Path(temp_name))["verdict"])

    def test_vanilla_benchmark_control_is_unscaffolded_and_mutating(self) -> None:
        import subprocess
        with tempfile.TemporaryDirectory() as temp_name:
            output = Path(temp_name) / "run"
            completed = subprocess.run([
                sys.executable, str(IMPL / "prepare_adaptive_run.py"),
                "--fixture", "open-world-record-parser", "--arm", "vanilla", "--output", str(output),
            ], text=True, capture_output=True, encoding="utf-8", errors="replace", timeout=60)
            self.assertEqual(0, completed.returncode, completed.stderr)
            manifest = json.loads((output / "run-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual([], manifest["agent_context_files"])
            self.assertFalse((output / "workspace/.agentic").exists())
            self.assertEqual((output / "workspace/task.md").read_text(encoding="utf-8-sig").rstrip(), (output / "prompt.txt").read_text(encoding="utf-8").rstrip())

    def test_critical_requires_approval_and_independent_verification(self) -> None:
        ledger = compile_ledger("- Preserve behavior.")
        req = ledger["requirements"][0]
        ok = [sys.executable, "-c", "raise SystemExit(0)"]
        evidence = {
            "mode": "critical",
            "capabilities": ["human-approval-boundaries", "independent-verifier"],
            "requirements": [{"requirement_id": req["id"], "status": "verified", "evidence": [{"kind": "behavior", "path": "proof.txt"}, {"kind": "test", "command": ok, "exit_code": 0}]}],
            "ambiguity_resolutions": [],
            "verification_runs": [{"command": ok, "exit_code": 0}],
            "completion_claim": {"status": "ready"},
        }
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            (root / "proof.txt").write_text("proof", encoding="utf-8")
            blocked = validate(ledger, evidence, root)
            self.assertEqual("FAIL", blocked["verdict"])
            blocked_ids = {row["id"] for row in blocked["failures"]}
            self.assertIn("scope-approval", blocked_ids)
            self.assertIn("independent-verification", blocked_ids)
            evidence["scope_approval"] = {"status": "approved", "approved_by": "human"}
            evidence["independent_verification"] = {"status": "PASS", "verifier_profile": "adversarial-review"}
            self.assertEqual("PASS", validate(ledger, evidence, root)["verdict"])

    def test_lite_gets_core_and_lossless_compact_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            task = root / "task.md"
            task.write_text("- Update the local documentation.\n- Preserve the example.", encoding="utf-8")
            full = compile_ledger(task.read_text(encoding="utf-8"), str(task))
            result = prepare(task, root, root / ".agentic", [], "lite")
            compact = json.loads((root / ".agentic/objective-ledger.json").read_text(encoding="utf-8"))
            manifest = json.loads((root / ".agentic/context-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("lite", result["mode"])
            self.assertTrue((root / ".agentic/core.md").is_file())
            self.assertEqual("compact", manifest["ledger_profile"])
            self.assertFalse(manifest["loop_enabled"])
            self.assertFalse((root / ".agentic/check-suite.json").exists())
            self.assertEqual({r["id"] for r in full["requirements"]}, {r["id"] for r in compact["requirements"]})
            self.assertLess(len(json.dumps(compact)), len(json.dumps(full)))

    def test_gate_reruns_check_suite_and_fails_closed(self) -> None:
        ledger = compile_ledger("- Change the public API safely.")
        req = ledger["requirements"][0]
        ok = [sys.executable, "-c", "raise SystemExit(0)"]
        evidence = {
            "mode": "standard",
            "capabilities": ["verification-loop"],
            "requirements": [{"requirement_id": req["id"], "status": "verified", "evidence": [{"kind": "test", "command": ok, "exit_code": 0}]}],
            "ambiguity_resolutions": [], "verification_runs": [{"command": ok, "exit_code": 0}],
            "completion_claim": {"status": "ready"},
        }
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            # No suite at all: the capability is active, so the gate fails closed.
            missing = validate(ledger, evidence, root)
            self.assertEqual("FAIL", missing["verdict"])
            self.assertTrue(any(row["id"] == "check-suite" for row in missing["failures"]))
            # A green frozen suite passes.
            self.assertEqual("PASS", validate(ledger, evidence, root, check_suite=green_suite())["verdict"])
            # A failing check fails the gate even though every agent claim is green.
            failing = green_suite()
            failing["checks"].append({"id": "regression", "kind": "acceptance", "authored_by": "harness",
                                      "command": [sys.executable, "-c", "raise SystemExit(1)"]})
            failing["harness_freeze_sha256"] = harness_freeze_sha256(failing)
            report = validate(ledger, evidence, root, check_suite=failing)
            self.assertEqual("FAIL", report["verdict"])
            self.assertTrue(any(row["id"] == "check:regression" for row in report["failures"]))
            # A tampered suite (weakened check, stale digest) fails integrity.
            tampered = green_suite()
            tampered["checks"][0]["command"] = [sys.executable, "-c", "raise SystemExit(0) # weakened"]
            report = validate(ledger, evidence, root, check_suite=tampered)
            self.assertEqual("FAIL", report["verdict"])
            self.assertTrue(any(row["id"] == "check-suite-integrity" for row in report["failures"]))

    def test_multi_session_standard_requires_checkpoint_and_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            task = root / "task.md"
            task.write_text("Continue this multi-session implementation and resume from a durable checkpoint.", encoding="utf-8")
            prepare(task, root, root / ".agentic", [], None)
            decision = json.loads((root / ".agentic/mode-decision.json").read_text(encoding="utf-8"))
            self.assertEqual("standard", decision["mode"])
            self.assertIn("durable-checkpoints", decision["capabilities"])
            checkpoint = json.loads((root / ".agentic/checkpoint.json").read_text(encoding="utf-8"))
            handoff = json.loads((root / ".agentic/session-handoff.json").read_text(encoding="utf-8"))
            self.assertTrue(checkpoint["required"])
            self.assertTrue(handoff["required"])
            self.assertEqual("pending", checkpoint["status"])
            self.assertEqual("pending", handoff["status"])

    def test_standard_prepares_frozen_check_suite_and_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            task = root / "task.md"
            task.write_text("- Build an open-world parser for unseen values without an allowlist.\n- Add tests.", encoding="utf-8")
            (root / "tests").mkdir()
            (root / "tests" / "test_public.py").write_text("import unittest\n\nclass T(unittest.TestCase):\n    def test_ok(self):\n        pass\n", encoding="utf-8")
            output = root / ".agentic"
            result = prepare(task, root, output, [], None)
            self.assertEqual("standard", result["mode"])
            suite = json.loads((output / "check-suite.json").read_text(encoding="utf-8"))
            enforcement = json.loads((output / "enforcement.json").read_text(encoding="utf-8"))
            kinds = {row["id"] for row in suite["checks"]}
            self.assertIn("symbol-sweep", kinds)
            self.assertIn("public-tests", kinds)
            self.assertEqual(suite["harness_freeze_sha256"], enforcement["check_suite_freeze_sha256"])
            self.assertEqual(harness_freeze_sha256(suite), suite["harness_freeze_sha256"])
            record = json.loads((output / "baseline-record.json").read_text(encoding="utf-8"))
            self.assertEqual("complete", record["snapshot"])
            self.assertTrue((output / "baseline-workspace/tests/test_public.py").is_file())
            for tool in ("harness_checks.py", "verification_loop.py", "pre_submit_gate.py"):
                self.assertTrue((output / tool).is_file(), tool)

    def test_context_pack_respects_budget_and_hides_graders(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            task = root / "task.md"
            task.write_text("- Build an open-world parser for unseen values without an allowlist.\n- Add tests.", encoding="utf-8")
            (root / "tests").mkdir()
            (root / "tests" / "public_test.py").write_text("assert True\n", encoding="utf-8")
            output = root / ".agentic"
            result = prepare(task, root, output, [], None)
            manifest = json.loads((output / "context-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("standard", result["mode"])
            self.assertLessEqual(manifest["context_characters"], manifest["context_budget"]["max_characters"])
            self.assertFalse(any("hidden" in str(path).lower() or "grade.py" in str(path).lower() for path in output.rglob("*")))
            self.assertTrue((output / "pre_submit_gate.py").exists())

    def test_failure_attribution_protects_invalid_oracles(self) -> None:
        data = {
            "campaign_id": "x",
            "execution_integrity": "PASS",
            "fixture_issues": {"f": {"spec_ambiguity_checks": ["input"], "grader_failure_checks": ["docs"]}},
            "runs": [{"run_id": "r", "fixture": "f", "arm": "critical", "failed_checks": ["input", "docs"]}],
        }
        result = attribute(data)
        self.assertEqual("UNINTERPRETABLE_FOR_AFFECTED_CHECKS", result["quality_interpretation"])
        self.assertEqual(["SPEC_AMBIGUITY", "GRADER_FAILURE"], [row["category"] for row in result["attributions"]])

    def test_model_policy_uses_profiles_and_blocks_stale_automation(self) -> None:
        from datetime import datetime, timezone
        current = resolve("anthropic-claude-code", "fast-low-risk", "low", now=datetime(2026, 7, 14, tzinfo=timezone.utc))
        self.assertTrue(current["automation_allowed"])
        stale = resolve("anthropic-claude-code", "fast-low-risk", "low", now=datetime(2030, 1, 1, tzinfo=timezone.utc))
        self.assertFalse(stale["automation_allowed"])
        modes_text = (IMPL / "modes.json").read_text(encoding="utf-8").lower()
        for volatile_id in ("gpt-", "claude-", "sonnet", "opus", "fable"):
            self.assertNotIn(volatile_id, modes_text)


if __name__ == "__main__":
    unittest.main()
