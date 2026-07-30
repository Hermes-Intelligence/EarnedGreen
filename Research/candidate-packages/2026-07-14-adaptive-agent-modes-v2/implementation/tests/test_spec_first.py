"""Spec-first planning layer: clarity axis, spec synthesis, ledger freeze."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
IMPL = HERE.parent
sys.path.insert(0, str(IMPL))

from adaptive_router import route  # noqa: E402
from objective_compiler import compile_ledger  # noqa: E402
from prepare_context import prepare  # noqa: E402
from pre_submit_gate import validate  # noqa: E402
from spec_synthesis import (  # noqa: E402
    compile_spec,
    freeze_record,
    freeze_violations,
    spec_freeze_sha256,
    validate_spec,
)

UNDERSPECIFIED_PROMPTS = [
    # The realistic owner prompts that historically cost many human iterations.
    "Add a new source gamma to the pipeline producing the same product table; keep everything consistent with how the existing sources work.",
    "Build the DC WIRE product like the existing NY product, end to end, ready for production.",
    "Adapt the NY Medicaid state adapter to load the New Jersey enrollment files.",
    "Create a new integration for the vendor webhook events, same as the existing poller.",
]
WELL_SPECIFIED_PROMPTS = [
    "Change a public API response schema, preserve backward-compatible consumers and test the integration.",
    "Fix the login bug: when the session cookie is expired the endpoint must not raise and returns exactly HTTP 401.",
    "Rename a private local variable as a mechanical change.",
    "Explain only how a production deployment would work; do not deploy or change files.",
]

TASK = (
    "# Task: add the gamma source\n\n"
    "Add a new source gamma to the pipeline producing the same product table; "
    "keep everything consistent with how the existing sources work.\n\n"
    "Do not modify task.md.\n"
)

OK_COMMAND = [sys.executable, "-c", "raise SystemExit(0)"]
FAIL_COMMAND = [sys.executable, "-c", "raise SystemExit(3)"]


def make_workspace(root: Path) -> Path:
    (root / "task.md").write_text(TASK, encoding="utf-8")
    (root / "src").mkdir(exist_ok=True)
    (root / "src" / "changelog.py").write_text(
        '"""APPEND-ONLY log: a restatement is a new row, never an update."""\n', encoding="utf-8")
    (root / "src" / "feed.py").write_text(
        '"""Feed loader: an error payload must fail loudly, never load zero rows."""\n', encoding="utf-8")
    return root


def filled_spec(root: Path) -> dict:
    spec = compile_spec(TASK, str(root / "task.md"))
    spec["status"] = "filled"
    spec["objective_restatement"] = "Wire the gamma source into the pipeline with full parity to the existing sources, including their implicit conventions."
    spec["surface_inventory"] = [
        {"id": "io-feed", "kind": "external-io", "surface": "gamma payload load path",
         "evidence_file": "src/feed.py"},
        {"id": "log-state", "kind": "persistence", "surface": "append-only change log",
         "evidence_file": "src/changelog.py"},
    ]
    spec["convention_inventory"] = [
        {"convention": "the change log is append-only; a restatement is a new row",
         "source_file_or_evidence": "src/changelog.py",
         "applies_because": "gamma amend records restate earlier events"},
    ]
    spec["decision_points"] = [
        {"id": "amend-handling", "question": "what does a gamma amend record do to the log?",
         "options": ["overwrite the earlier row", "append a new restate row"],
         "pinned_choice": "append a new restate row",
         "pinned_by": "src/changelog.py docstring: APPEND-ONLY, restatement is a new row"},
    ]
    spec["risk_register"] = [
        {"id": "r-silent-zero", "risk": "an error-shaped payload loads zero rows silently",
         "likelihood": "medium", "surface_id": "io-feed",
         "mitigation": "raise FeedError on error-shaped or empty payloads",
         "verification": "acceptance test at-ok re-executed by the gate"},
        {"id": "r-log-rewrite", "risk": "amend handling rewrites log history in place",
         "likelihood": "medium", "surface_id": "log-state",
         "mitigation": "route every event through changelog.record",
         "verification": "acceptance test at-ok exercises a halt+amend pair"},
    ]
    spec["rejected_approaches"] = [
        {"approach": "retry loop around the feed load", "why_rejected": "over-engineering; the feed is replayed upstream",
         "evidence": "src/feed.py"},
    ]
    spec["acceptance_tests"] = [
        {"id": "at-ok", "command": list(OK_COMMAND), "expected": "exit 0: full frozen scope behaves"},
    ]
    spec["coverage_argument"] = "Two surfaces only: the load path and the log. No UI, no schema, no concurrency surface exists in this miniature workspace; deliberately left out: packaging."
    spec["adversarial_review"] = {"status": "clear", "reviewed_by": "independent adversarial pass",
                                  "instructions": "", "findings": []}
    spec["frozen_ledger"]["requirements"].append(
        {"id": "REQ-DISC-APPENDLOG", "statement": "a gamma amend appends a restate row; the log is never rewritten",
         "source": "discovered", "status": "pending"})
    return spec


def base_evidence(ledger: dict) -> dict:
    return {
        "mode": "standard",
        "capabilities": ["minimal-core", "precision-router", "objective-ledger", "focused-verification", "pre-submit-gate", "spec-synthesis"],
        "requirements": [
            {"requirement_id": row["id"], "status": "verified",
             "evidence": [{"kind": "test", "command": list(OK_COMMAND), "exit_code": 0}]}
            for row in ledger["requirements"]
        ],
        "ambiguity_resolutions": [
            {"ambiguity_id": row["id"], "resolution": "pinned by the spec's convention inventory", "authority": "owner-approved spec"}
            for row in ledger["ambiguities"]
        ],
        "verification_runs": [{"command": list(OK_COMMAND), "exit_code": 0}],
        "completion_claim": {"status": "ready"},
    }


class ClarityClassificationTests(unittest.TestCase):
    def test_underspecified_hermes_style_prompts(self) -> None:
        for prompt in UNDERSPECIFIED_PROMPTS:
            with self.subTest(prompt=prompt):
                result = route(prompt)
                self.assertEqual("underspecified", result["analysis"]["axes"]["clarity"])
                self.assertGreaterEqual(result["mode_rank"], 1, "underspecified mutating work runs in standard or above")
                self.assertIn("spec-synthesis", result["capabilities"])

    def test_well_specified_prompts(self) -> None:
        for prompt in WELL_SPECIFIED_PROMPTS:
            with self.subTest(prompt=prompt):
                result = route(prompt)
                self.assertEqual("well-specified", result["analysis"]["axes"]["clarity"])
                self.assertNotIn("spec-synthesis", result["capabilities"])

    def test_v4_fixture_task_is_well_specified(self) -> None:
        task = (IMPL / "mode-boundary-fixture-v4/public/task.md").read_text(encoding="utf-8-sig")
        result = route(task)
        self.assertEqual("well-specified", result["analysis"]["axes"]["clarity"])
        self.assertNotIn("spec-synthesis", result["capabilities"])

    def test_clarity_fixture_task_is_underspecified(self) -> None:
        task = (IMPL / "mode-boundary-fixture-clarity/public/task.md").read_text(encoding="utf-8-sig")
        result = route(task)
        self.assertEqual("underspecified", result["analysis"]["axes"]["clarity"])
        self.assertIn("spec-synthesis", result["capabilities"])

    def test_forced_lite_never_receives_spec_synthesis(self) -> None:
        result = route(UNDERSPECIFIED_PROMPTS[0], forced_mode="lite")
        self.assertNotIn("spec-synthesis", result["capabilities"])

    def test_clarity_never_changes_the_human_gate(self) -> None:
        result = route(UNDERSPECIFIED_PROMPTS[0])
        self.assertFalse(result["model_routing"]["human_gate"])

    def test_mode_cases_unchanged(self) -> None:
        cases = json.loads((HERE / "mode-cases.json").read_text(encoding="utf-8"))["cases"]
        for case in cases:
            with self.subTest(case=case["id"]):
                result = route(case["task"], case.get("changed_paths"))
                self.assertEqual(case["expected_mode"], result["mode"])


class SpecValidationTests(unittest.TestCase):
    def test_valid_spec_passes_and_emits_freeze_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = make_workspace(Path(temp_name))
            outcome = validate_spec(filled_spec(root), root, TASK)
            self.assertEqual("PASS", outcome["verdict"], outcome["failures"])
            self.assertRegex(outcome["spec_sha256"], r"^[0-9A-F]{64}$")

    def assert_fails(self, spec: dict, root: Path, fragment: str) -> None:
        outcome = validate_spec(spec, root, TASK)
        self.assertEqual("FAIL", outcome["verdict"])
        reasons = " | ".join(f"{row['id']}: {row['reason']}" for row in outcome["failures"])
        self.assertIn(fragment, reasons, reasons)

    def test_fail_closed_cases(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = make_workspace(Path(temp_name))
            spec = filled_spec(root)
            spec["decision_points"][0]["pinned_choice"] = ""
            self.assert_fails(spec, root, "no pinned_choice")

            spec = filled_spec(root)
            spec["decision_points"][0]["owner_decision_required"] = True
            self.assert_fails(spec, root, "owner decision required")

            spec = filled_spec(root)
            spec["risk_register"][0]["verification"] = ""
            self.assert_fails(spec, root, "no verification")

            spec = filled_spec(root)
            spec["convention_inventory"][0]["source_file_or_evidence"] = "src/does_not_exist.py"
            self.assert_fails(spec, root, "evidence file not found")

            spec = filled_spec(root)
            spec["frozen_ledger"]["requirements"] = [
                row for row in spec["frozen_ledger"]["requirements"] if row["source"] != "task-text"
            ][:1] or spec["frozen_ledger"]["requirements"][-1:]
            self.assert_fails(spec, root, "task-text requirement silently dropped")

            spec = filled_spec(root)
            spec["surface_inventory"].append({"id": "orphan", "kind": "cache", "surface": "an uncovered surface", "evidence_file": "src/feed.py"})
            self.assert_fails(spec, root, "no risk_register entry")

            spec = filled_spec(root)
            spec["coverage_argument"] = ""
            self.assert_fails(spec, root, "coverage")

            spec = filled_spec(root)
            spec["adversarial_review"]["status"] = "pending"
            self.assert_fails(spec, root, "adversarial spec review is not clear")

            spec = filled_spec(root)
            spec["acceptance_tests"] = []
            self.assert_fails(spec, root, "runnable commands")

            spec = filled_spec(root)
            spec["risk_register"][1]["risk"] = spec["risk_register"][0]["risk"]
            self.assert_fails(spec, root, "duplicate risk statement")

            spec = filled_spec(root)
            spec["risk_register"][0]["surface_id"] = "nonexistent-surface"
            self.assert_fails(spec, root, "does not trace")

    def test_freeze_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = make_workspace(Path(temp_name))
            spec = filled_spec(root)
            freeze = freeze_record(spec)
            self.assertEqual(freeze["spec_sha256"], spec_freeze_sha256(spec))
            self.assertEqual([], freeze_violations(spec, freeze))

            # Additions are allowed (hash changes, no violation).
            grown = filled_spec(root)
            grown["frozen_ledger"]["requirements"].append(
                {"id": "REQ-DISC-EXTRA", "statement": "another discovered requirement", "source": "discovered", "status": "pending"})
            self.assertNotEqual(freeze["spec_sha256"], spec_freeze_sha256(grown))
            self.assertEqual([], freeze_violations(grown, freeze))

            # Row deletion is a violation.
            shrunk = filled_spec(root)
            removed = shrunk["frozen_ledger"]["requirements"].pop()
            violations = freeze_violations(shrunk, freeze)
            self.assertTrue(any("was removed" in violation for violation in violations), violations)

            # Status downgrade is a violation ...
            downgraded = filled_spec(root)
            downgraded["frozen_ledger"]["requirements"][-1]["status"] = "not_applicable"
            violations = freeze_violations(downgraded, freeze)
            self.assertTrue(any("downgraded" in violation for violation in violations), violations)

            # ... unless an owner_scope_change records explicit human approval.
            downgraded["frozen_ledger"]["owner_scope_changes"] = [
                {"requirement_id": removed["id"], "approved_by": "owner", "reason": "scope cut agreed on 2026-07-14"}]
            self.assertEqual([], freeze_violations(downgraded, freeze))

            # Statement rewrite is a violation.
            rewritten = filled_spec(root)
            rewritten["frozen_ledger"]["requirements"][0]["statement"] = "a materially weaker restatement"
            violations = freeze_violations(rewritten, freeze)
            self.assertTrue(any("rewritten" in violation for violation in violations), violations)


class LedgerFreezeGateTests(unittest.TestCase):
    def run_gate(self, spec: dict, evidence: dict | None = None, freeze: dict | None = None) -> dict:
        with tempfile.TemporaryDirectory() as temp_name:
            root = make_workspace(Path(temp_name))
            ledger = compile_ledger(TASK, "task.md")
            evidence = evidence or base_evidence(ledger)
            freeze = freeze or freeze_record(filled_spec(root))
            return validate(ledger, evidence, root, task_path=root / "task.md",
                            spec=spec, spec_freeze=freeze)

    def test_honest_full_scope_completion_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = make_workspace(Path(temp_name))
            spec = filled_spec(root)
            result = self.run_gate(spec)
            self.assertEqual("PASS", result["verdict"], result["failures"])
            self.assertTrue(result["completion_allowed"])

    def test_scope_shrink_attempt_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = make_workspace(Path(temp_name))
            spec = filled_spec(root)
            spec["frozen_ledger"]["requirements"] = [
                row for row in spec["frozen_ledger"]["requirements"] if row["id"] != "REQ-DISC-APPENDLOG"]
            result = self.run_gate(spec)
            self.assertEqual("FAIL", result["verdict"])
            reasons = " | ".join(row["reason"] for row in result["failures"])
            self.assertIn("was removed without an owner_scope_change", reasons)

    def test_evidence_downgrade_of_frozen_requirement_fails_without_owner_change(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = make_workspace(Path(temp_name))
            ledger = compile_ledger(TASK, "task.md")
            evidence = base_evidence(ledger)
            victim = ledger["requirements"][0]["id"]
            evidence["requirements"][0] = {"requirement_id": victim, "status": "not_applicable", "reason": "decided to skip"}
            spec = filled_spec(root)
            result = self.run_gate(spec, evidence=evidence)
            self.assertEqual("FAIL", result["verdict"])
            reasons = " | ".join(row["reason"] for row in result["failures"])
            self.assertIn("without an owner_scope_change", reasons)
            # An explicit owner_scope_change makes the same downgrade legitimate.
            spec["frozen_ledger"]["owner_scope_changes"] = [
                {"requirement_id": victim, "approved_by": "owner", "reason": "descoped after review"}]
            result = self.run_gate(spec, evidence=evidence)
            self.assertEqual("PASS", result["verdict"], result["failures"])

    def test_failing_acceptance_test_fails_the_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = make_workspace(Path(temp_name))
            spec = filled_spec(root)
            spec["acceptance_tests"].append({"id": "at-broken", "command": list(FAIL_COMMAND), "expected": "exit 0"})
            freeze = freeze_record(spec)
            result = self.run_gate(spec, freeze=freeze)
            self.assertEqual("FAIL", result["verdict"])
            reasons = " | ".join(f"{row['id']}: {row['reason']}" for row in result["failures"])
            self.assertIn("acceptance:at-broken", reasons)

    def test_missing_freeze_record_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = make_workspace(Path(temp_name))
            ledger = compile_ledger(TASK, "task.md")
            result = validate(ledger, base_evidence(ledger), root, task_path=root / "task.md",
                              spec=filled_spec(root), spec_freeze=None)
            self.assertEqual("FAIL", result["verdict"])
            reasons = " | ".join(row["reason"] for row in result["failures"])
            self.assertIn("frozen ledger was never recorded", reasons)

    def test_declared_capability_without_spec_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = make_workspace(Path(temp_name))
            ledger = compile_ledger(TASK, "task.md")
            result = validate(ledger, base_evidence(ledger), root, task_path=root / "task.md")
            self.assertEqual("FAIL", result["verdict"])
            reasons = " | ".join(row["reason"] for row in result["failures"])
            self.assertIn("no spec.json", reasons)


class SpecSynthesisCliTests(unittest.TestCase):
    def test_validate_cli_freezes_then_blocks_shrink(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = make_workspace(Path(temp_name))
            spec_path = root / "spec.json"
            freeze_path = root / "spec-freeze.json"
            spec = filled_spec(root)
            spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
            command = [sys.executable, str(IMPL / "spec_synthesis.py"), "validate",
                       "--spec", str(spec_path), "--workspace", str(root),
                       "--task-file", str(root / "task.md"), "--freeze", str(freeze_path)]
            first = subprocess.run(command, text=True, capture_output=True, encoding="utf-8", errors="replace", timeout=60)
            self.assertEqual(0, first.returncode, first.stdout[-2000:] + first.stderr[-2000:])
            self.assertTrue(freeze_path.is_file())
            second = subprocess.run(command, text=True, capture_output=True, encoding="utf-8", errors="replace", timeout=60)
            self.assertEqual(0, second.returncode, second.stdout[-2000:] + second.stderr[-2000:])
            spec["frozen_ledger"]["requirements"] = [
                row for row in spec["frozen_ledger"]["requirements"] if row["id"] != "REQ-DISC-APPENDLOG"]
            spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
            third = subprocess.run(command, text=True, capture_output=True, encoding="utf-8", errors="replace", timeout=60)
            self.assertNotEqual(0, third.returncode)
            self.assertIn("owner_scope_change", third.stdout)


class PrepareContextSpecFirstTests(unittest.TestCase):
    def test_underspecified_task_gets_spec_scaffold_and_enforcement(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = make_workspace(Path(temp_name))
            output = root / ".agentic"
            result = prepare(root / "task.md", root, output, [], None)
            decision = json.loads((output / "mode-decision.json").read_text(encoding="utf-8"))
            self.assertIn("spec-synthesis", decision["capabilities"])
            self.assertGreaterEqual(decision["mode_rank"], 1, "spec synthesis runs in standard or above")
            for name in ("spec.json", "spec.md", "spec_synthesis.py", "objective_compiler.py", "risk-discovery.md"):
                self.assertTrue((output / name).is_file(), name)
            spec = json.loads((output / "spec.json").read_text(encoding="utf-8"))
            self.assertEqual("scaffold", spec["status"])
            self.assertTrue(all(row["source"] == "task-text" for row in spec["frozen_ledger"]["requirements"]))
            enforcement = json.loads((output / "enforcement.json").read_text(encoding="utf-8"))
            requires = " | ".join(enforcement["completion_requires"])
            self.assertIn("ledger freeze intact", requires)
            self.assertIn("acceptance test re-executed", requires)
            prompt = (output / "agent_prompt_appendix.txt").read_text(encoding="utf-8")
            self.assertIn("SPEC-FIRST CONTRACT", prompt)
            self.assertIn("owner_scope_changes", prompt)
            evidence = json.loads((output / "evidence.json").read_text(encoding="utf-8"))
            self.assertIn("spec-synthesis", evidence["capabilities"])
            # risk-discovery is illustrative, never a rubric.
            module_text = (output / "risk-discovery.md").read_text(encoding="utf-8")
            self.assertIn("never be treated as a rubric", module_text)

    def test_well_specified_task_gets_no_spec_scaffold(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            task = root / "task.md"
            task.write_text("- Return the value and test invalid input.\n- Keep the wrapper.", encoding="utf-8")
            output = root / ".agentic"
            prepare(task, root, output, [], None)
            self.assertFalse((output / "spec.json").exists())
            self.assertFalse((output / "risk-discovery.md").exists())


if __name__ == "__main__":
    unittest.main()
