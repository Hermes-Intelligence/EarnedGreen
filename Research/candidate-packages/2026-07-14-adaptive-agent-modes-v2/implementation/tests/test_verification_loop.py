from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
IMPL = HERE.parent
sys.path.insert(0, str(IMPL))

import harness_checks
import verification_loop

OK = [sys.executable, "-c", "raise SystemExit(0)"]
FAIL = [sys.executable, "-c", "raise SystemExit(1)"]


def make_suite(checks: list[dict], config: dict | None = None) -> dict:
    suite = {"schema_version": 1, "config": config or {}, "checks": checks}
    suite["harness_freeze_sha256"] = harness_checks.harness_freeze_sha256(suite)
    return suite


class HarnessChecksTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self._tmp.name)
        (self.workspace / ".agentic").mkdir()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def write(self, relative: str, content: str) -> Path:
        target = self.workspace / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def snapshot(self) -> dict:
        record = harness_checks.snapshot_baseline(self.workspace, self.workspace / ".agentic/baseline-workspace")
        (self.workspace / ".agentic/baseline-record.json").write_text(json.dumps(record), encoding="utf-8")
        return record

    def test_acceptance_pass_and_fail(self) -> None:
        suite = make_suite([
            {"id": "ok", "kind": "acceptance", "authored_by": "harness", "command": OK},
            {"id": "bad", "kind": "acceptance", "authored_by": "harness", "command": FAIL},
        ])
        report = harness_checks.run_suite(suite, self.workspace)
        self.assertFalse(report["green"])
        self.assertEqual(["bad"], report["failing_check_ids"])

    def test_differential_catches_silent_regression(self) -> None:
        # BEFORE emits two fields; the "agent change" silently rewrites one of
        # them (the medi-ny therapeutic_class shape). The differential must
        # fail with the changed line, deterministically.
        self.write("parser.py", "import json\nprint(json.dumps({'name': 'DRUG 10MG', 'therapeutic_class': 'ANALGESICS'}))\n")
        self.snapshot()
        self.write("parser.py", "import json\nprint(json.dumps({'name': 'DRUG', 'therapeutic_class': 'WRONG'}))\n")
        suite = make_suite([{
            "id": "diff", "kind": "differential", "authored_by": "harness",
            "command": [sys.executable, "parser.py"],
            "expected_change_patterns": [r"'?\"?name\"?'?"],
        }])
        report = harness_checks.run_suite(suite, self.workspace)
        self.assertFalse(report["green"])
        detail = report["checks"][0]["failures"][0]
        self.assertIn("therapeutic_class", detail["unexpected_diff"])
        self.assertNotIn('"name"', detail["unexpected_diff"])

    def test_differential_accepts_declared_changes_only(self) -> None:
        self.write("parser.py", "print('name=DRUG 10MG')\n")
        self.snapshot()
        self.write("parser.py", "print('name=DRUG')\n")
        suite = make_suite([{
            "id": "diff", "kind": "differential", "authored_by": "harness",
            "command": [sys.executable, "parser.py"],
            "expected_change_patterns": [r"name="],
        }])
        self.assertTrue(harness_checks.run_suite(suite, self.workspace)["green"])

    def test_differential_fails_closed_without_baseline(self) -> None:
        suite = make_suite([{"id": "diff", "kind": "differential", "authored_by": "harness", "command": OK}])
        report = harness_checks.run_suite(suite, self.workspace)
        self.assertFalse(report["green"])
        self.assertIn("baseline workspace unavailable", report["checks"][0]["failures"][0]["reason"])

    def test_symbol_sweep_flags_unvisited_consumer(self) -> None:
        # lib.py defines emit(); consumer.py calls it; the agent edits lib.py
        # only. The sweep must name consumer.py until it is either changed or
        # recorded as inspected with a note (F-2026-07-12-013).
        self.write("lib.py", "def emit():\n    return 1\n")
        self.write("consumer.py", "from lib import emit\nprint(emit())\n")
        self.snapshot()
        self.write("lib.py", "def emit():\n    return 2\n")
        suite = make_suite([{"id": "sweep", "kind": "symbol-sweep", "authored_by": "harness"}])
        report = harness_checks.run_suite(suite, self.workspace)
        self.assertFalse(report["green"])
        self.assertIn("consumer.py", report["checks"][0]["failures"][0]["path"])
        evidence = {"consumer_inspections": [{"path": "consumer.py", "note": "return-type unchanged; call site verified"}]}
        report = harness_checks.run_suite(suite, self.workspace, evidence=evidence)
        self.assertTrue(report["green"], report["checks"])

    def test_symbol_sweep_ignores_untouched_symbols_in_a_touched_file(self) -> None:
        # Found on a fresh-repo run: adding `discount` to a module must NOT
        # flag every consumer of `total`, which nobody modified. Symbol
        # granularity, not file granularity - noise trains people to ignore
        # the sweep.
        self.write("cart.py", "def total(items):\n    return sum(items)\n")
        self.write("consumer.py", "from cart import total\nprint(total([1]))\n")
        self.snapshot()
        self.write("cart.py", "def total(items):\n    return sum(items)\n\n\ndef discount(x):\n    return x * 0.9\n")
        suite = make_suite([{"id": "sweep", "kind": "symbol-sweep", "authored_by": "harness"}])
        report = harness_checks.run_suite(suite, self.workspace)
        self.assertTrue(report["green"], report["checks"][0]["failures"])

    def test_symbol_sweep_flags_a_consumer_when_the_definition_body_changes(self) -> None:
        self.write("cart.py", "def total(items):\n    return sum(items)\n")
        self.write("consumer.py", "from cart import total\nprint(total([1]))\n")
        self.snapshot()
        self.write("cart.py", "def total(items):\n    return sum(items) * 2\n")
        suite = make_suite([{"id": "sweep", "kind": "symbol-sweep", "authored_by": "harness"}])
        report = harness_checks.run_suite(suite, self.workspace)
        self.assertFalse(report["green"])
        self.assertIn("consumer.py", report["checks"][0]["failures"][0]["path"])

    def test_symbol_sweep_ignores_untouched_symbols(self) -> None:
        self.write("lib.py", "def emit():\n    return 1\n")
        self.write("other.py", "def helper():\n    return 0\n")
        self.write("consumer.py", "from other import helper\n")
        self.snapshot()
        self.write("lib.py", "def emit():\n    return 2\n")
        suite = make_suite([{"id": "sweep", "kind": "symbol-sweep", "authored_by": "harness"}])
        self.assertTrue(harness_checks.run_suite(suite, self.workspace)["green"])

    def test_symbol_sweep_inspection_requires_note(self) -> None:
        self.write("lib.py", "def emit():\n    return 1\n")
        self.write("consumer.py", "from lib import emit\n")
        self.snapshot()
        self.write("lib.py", "def emit():\n    return 2\n")
        suite = make_suite([{"id": "sweep", "kind": "symbol-sweep", "authored_by": "harness"}])
        evidence = {"consumer_inspections": [{"path": "consumer.py", "note": "  "}]}
        self.assertFalse(harness_checks.run_suite(suite, self.workspace, evidence=evidence)["green"])

    def test_property_check(self) -> None:
        self.write("sample.txt", "DRUG (CONTINUED\nON NEXT LINE)\n")
        self.write("prop.py", "import sys,pathlib\ntext=pathlib.Path('sample.txt').read_text()\nsys.exit(1 if '(CONTINUED' in text else 0)\n")
        suite = make_suite([{"id": "prop", "kind": "property", "authored_by": "harness", "command": [sys.executable, "prop.py"]}])
        report = harness_checks.run_suite(suite, self.workspace)
        self.assertFalse(report["green"])

    def test_finding_requires_proof_or_waiver(self) -> None:
        suite = make_suite([{"id": "finding:V1", "kind": "finding", "authored_by": "harness", "claim": "output drops rows"}])
        report = harness_checks.run_suite(suite, self.workspace, resolutions={})
        self.assertFalse(report["green"])
        # Prose alone must not resolve it.
        report = harness_checks.run_suite(suite, self.workspace, resolutions={"finding:V1": {"note": "fixed it, trust me"}})
        self.assertFalse(report["green"])
        # A proving command that passes resolves it.
        report = harness_checks.run_suite(suite, self.workspace, resolutions={"finding:V1": {"command": OK}})
        self.assertTrue(report["green"])
        # A failing proving command keeps it failing.
        report = harness_checks.run_suite(suite, self.workspace, resolutions={"finding:V1": {"command": FAIL}})
        self.assertFalse(report["green"])
        # An explicit owner waiver with a reason resolves it.
        report = harness_checks.run_suite(suite, self.workspace, resolutions={"finding:V1": {"waived_by": "owner", "reason": "accepted risk"}})
        self.assertTrue(report["green"])

    def test_suite_tamper_detection(self) -> None:
        suite = make_suite([{"id": "bad", "kind": "acceptance", "authored_by": "harness", "command": FAIL}])
        self.assertEqual([], harness_checks.verify_suite_integrity(suite))
        # Agent weakens the harness check: digest mismatch.
        tampered = json.loads(json.dumps(suite))
        tampered["checks"][0]["command"] = OK
        problems = harness_checks.verify_suite_integrity(tampered)
        self.assertTrue(any("modified after freeze" in row for row in problems))
        # Agent raises its own iteration budget: also digest-protected.
        tampered = json.loads(json.dumps(suite))
        tampered["config"] = {"max_iterations": 999}
        problems = harness_checks.verify_suite_integrity(tampered)
        self.assertTrue(any("modified after freeze" in row for row in problems))
        # Agent ADDITIONS are allowed.
        extended = json.loads(json.dumps(suite))
        extended["checks"].append({"id": "mine", "kind": "acceptance", "authored_by": "agent", "command": OK})
        self.assertEqual([], harness_checks.verify_suite_integrity(extended))
        # Removing the freeze digest entirely is caught.
        unfrozen = json.loads(json.dumps(suite))
        del unfrozen["harness_freeze_sha256"]
        self.assertTrue(harness_checks.verify_suite_integrity(unfrozen))


class VerificationLoopTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self._tmp.name)
        (self.workspace / ".agentic").mkdir()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def write_suite(self, checks: list[dict], config: dict | None = None) -> Path:
        suite = make_suite(checks, config)
        path = self.workspace / ".agentic/check-suite.json"
        path.write_text(json.dumps(suite, indent=2), encoding="utf-8")
        return path

    def test_iterate_to_green(self) -> None:
        flag = self.workspace / "fixed.txt"
        probe = [sys.executable, "-c", f"import pathlib,sys; sys.exit(0 if pathlib.Path(r'{flag}').exists() else 1)"]
        suite_path = self.write_suite([{"id": "probe", "kind": "acceptance", "authored_by": "harness", "command": probe}])
        first = verification_loop.step(suite_path, self.workspace)
        self.assertEqual("continue", first["verdict"])
        feedback = json.loads((self.workspace / ".agentic/loop-feedback.json").read_text(encoding="utf-8"))
        self.assertEqual("probe", feedback["failures"][0]["check_id"])
        flag.write_text("fixed", encoding="utf-8")  # the agent fixes the failure
        second = verification_loop.step(suite_path, self.workspace)
        self.assertEqual("green", second["verdict"])
        state = json.loads((self.workspace / ".agentic/loop-state.json").read_text(encoding="utf-8"))
        self.assertEqual(2, len(state["iterations"]))
        self.assertEqual("green", state["verdict"])

    def test_no_progress_termination(self) -> None:
        suite_path = self.write_suite(
            [{"id": "stuck", "kind": "acceptance", "authored_by": "harness", "command": FAIL}],
            config={"max_iterations": 10, "no_progress_limit": 2},
        )
        self.assertEqual("continue", verification_loop.step(suite_path, self.workspace)["verdict"])
        self.assertEqual("no-progress", verification_loop.step(suite_path, self.workspace)["verdict"])

    def test_iteration_budget_termination(self) -> None:
        # Failures keep CHANGING (no-progress never fires); the iteration
        # budget must still stop the loop.
        counter = self.workspace / "count.txt"
        vary = [sys.executable, "-c",
                ("import pathlib,sys\np=pathlib.Path(r'{0}')\nn=int(p.read_text()) if p.exists() else 0\n"
                 "p.write_text(str(n+1))\nprint('variant', n)\nsys.exit(1)").format(counter)]
        suite_path = self.write_suite(
            [{"id": "vary", "kind": "acceptance", "authored_by": "harness", "command": vary}],
            config={"max_iterations": 3, "no_progress_limit": 99},
        )
        self.assertEqual("continue", verification_loop.step(suite_path, self.workspace)["verdict"])
        self.assertEqual("continue", verification_loop.step(suite_path, self.workspace)["verdict"])
        self.assertEqual("iteration-budget", verification_loop.step(suite_path, self.workspace)["verdict"])

    def test_tampered_suite_is_integrity_failure(self) -> None:
        suite_path = self.write_suite([{"id": "bad", "kind": "acceptance", "authored_by": "harness", "command": FAIL}])
        suite = json.loads(suite_path.read_text(encoding="utf-8"))
        suite["checks"][0]["command"] = OK
        suite_path.write_text(json.dumps(suite), encoding="utf-8")
        result = verification_loop.step(suite_path, self.workspace)
        self.assertEqual("integrity-failure", result["verdict"])

    def test_ingest_findings_and_resolution_flow(self) -> None:
        suite_path = self.write_suite([{"id": "ok", "kind": "acceptance", "authored_by": "harness", "command": OK}])
        findings = self.workspace / ".agentic/verifier-findings.json"
        findings.write_text(json.dumps({"findings": [
            {"id": "V1", "severity": "blocking", "claim": "silent row drop on multiline names"},
        ]}), encoding="utf-8")
        result = verification_loop.ingest_findings(suite_path, findings)
        self.assertEqual(["finding:V1"], result["added"])
        # Suite stays integrity-valid after ingestion (digest recomputed) and
        # now fails until the finding is resolved with proof.
        self.assertEqual("continue", verification_loop.step(suite_path, self.workspace)["verdict"])
        (self.workspace / ".agentic/finding-resolutions.json").write_text(
            json.dumps({"resolutions": {"finding:V1": {"command": OK}}}), encoding="utf-8")
        self.assertEqual("green", verification_loop.step(suite_path, self.workspace)["verdict"])
        # Ingestion is idempotent.
        self.assertEqual([], verification_loop.ingest_findings(suite_path, findings)["added"])


if __name__ == "__main__":
    unittest.main()
