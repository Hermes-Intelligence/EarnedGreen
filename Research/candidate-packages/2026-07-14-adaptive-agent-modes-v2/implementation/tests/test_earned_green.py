"""Tests for earned-green: project detection, the vacuity gate, the necessity probe.

Every test here is zero-provider: the mechanisms are deterministic by design.
"""
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
import necessity_probe
import project_detect
from check_admission import admit, classify_failure, requirement_coverage


def suite_of(checks: list[dict]) -> dict:
    suite = {"schema_version": 1, "config": {}, "checks": [dict(c, authored_by="harness") for c in checks]}
    suite["harness_freeze_sha256"] = harness_checks.harness_freeze_sha256(suite)
    return suite


class ProjectDetectTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_detects_pytest_from_pyproject(self) -> None:
        (self.root / "pyproject.toml").write_text("[tool.pytest.ini_options]\ntestpaths = ['tests']\n", encoding="utf-8")
        detected = project_detect.detect(self.root)
        self.assertEqual("pytest", detected["test"]["runner"])
        self.assertIn("pytest", detected["test"]["command"])

    def test_detects_npm_but_ignores_the_placeholder_script(self) -> None:
        (self.root / "package.json").write_text(json.dumps({"scripts": {"test": "vitest run"}}), encoding="utf-8")
        self.assertEqual("npm", project_detect.detect(self.root)["test"]["runner"])
        # npm init's default script is not a test command; detecting it would
        # create an always-green acceptance check.
        (self.root / "package.json").write_text(
            json.dumps({"scripts": {"test": 'echo "Error: no test specified" && exit 1'}}), encoding="utf-8")
        self.assertNotEqual("npm", project_detect.detect(self.root)["test"]["runner"])

    def test_detects_unittest_layout(self) -> None:
        (self.root / "tests").mkdir()
        (self.root / "tests/test_x.py").write_text("import unittest\n", encoding="utf-8")
        detected = project_detect.detect(self.root)
        self.assertEqual("unittest", detected["test"]["runner"])
        self.assertEqual("tests", detected["test_dir"])

    def test_unknown_stack_reports_a_problem_instead_of_guessing(self) -> None:
        (self.root / "README.md").write_text("# nothing here\n", encoding="utf-8")
        detected = project_detect.detect(self.root)
        self.assertIsNone(detected["test"]["command"])
        self.assertIn("problem", detected["test"])

    def test_init_writes_project_json_and_verifies_the_baseline_is_green(self) -> None:
        (self.root / "tests").mkdir()
        (self.root / "tests/test_ok.py").write_text(
            "import unittest\n\nclass T(unittest.TestCase):\n    def test_ok(self): pass\n", encoding="utf-8")
        project = project_detect.init(self.root)
        self.assertTrue((self.root / ".agentic/project.json").is_file())
        self.assertTrue(project["test"]["baseline_run"]["green"])
        self.assertNotIn("problem", project["test"])

    def test_missing_runner_is_not_reported_as_failing_tests(self) -> None:
        # Found on the first real fresh-repo run: `python -m pytest` with pytest
        # uninstalled exits 1 exactly like a failing test. Calling that "your
        # tests are RED" is the misleading-diagnostic class this environment
        # exists to prevent.
        (self.root / "pyproject.toml").write_text("[tool.pytest.ini_options]\ntestpaths=['tests']\n", encoding="utf-8")
        run = project_detect.verify_test_command(self.root, ["python3", "-m", "definitely_not_installed_runner"])
        self.assertTrue(run["runner_missing"])
        self.assertFalse(run["ran"])
        self.assertNotIn("green", run)

    def test_init_flags_a_repo_whose_own_tests_are_already_red(self) -> None:
        (self.root / "tests").mkdir()
        (self.root / "tests/test_bad.py").write_text(
            "import unittest\n\nclass T(unittest.TestCase):\n    def test_bad(self): self.assertEqual(1, 2)\n",
            encoding="utf-8")
        project = project_detect.init(self.root)
        self.assertFalse(project["test"]["baseline_run"]["green"])
        self.assertIn("RED before any agent work", project["test"]["problem"])


class VacuityGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.baseline = Path(self._tmp.name)
        (self.baseline / "app.py").write_text("def greet():\n    return 'hi'\n", encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def check(self, body: str, **kwargs) -> dict:
        script = self.baseline / f"chk_{abs(hash(body))}.py"
        script.write_text(body, encoding="utf-8")
        row = {"id": kwargs.pop("id", "c1"), "kind": "acceptance",
               "command": [sys.executable, script.name],
               "requirement_ref": kwargs.pop("requirement_ref", "REQ-1"),
               "expectation": kwargs.pop("expectation", "red-before-green-after")}
        row.update(kwargs)
        return row

    def test_vacuous_check_is_rejected(self) -> None:
        # Passes on the pre-change code: proves nothing about new behaviour.
        row = self.check("assert True\n")
        result = admit([row], self.baseline)
        self.assertEqual("FAIL", result["verdict"])
        self.assertEqual("rejected", result["checks"][0]["verdict"])
        self.assertIn("VACUOUS", result["checks"][0]["reason"])

    def test_check_asserting_current_behaviour_is_rejected(self) -> None:
        row = self.check("import app\nassert app.greet() == 'hi'\n")
        self.assertEqual("rejected", admit([row], self.baseline)["checks"][0]["verdict"])

    def test_discriminating_check_is_admitted(self) -> None:
        # Asserts behaviour that does not exist yet, and FAILS with an assertion.
        row = self.check("import app\nassert app.greet() == 'hello world', 'greeting not updated'\n")
        result = admit([row], self.baseline)
        self.assertEqual("PASS", result["verdict"])
        self.assertEqual("admitted", result["checks"][0]["verdict"])
        self.assertEqual("assertion", result["checks"][0]["baseline_failure_kind"])

    def test_import_error_red_is_suspicious_not_admitted(self) -> None:
        # The trap: red only because the module is missing. An empty module
        # would turn it green, so it never proves the feature works.
        row = self.check("import brand_new_module\nassert brand_new_module.works()\n")
        result = admit([row], self.baseline)
        self.assertEqual("suspicious-red", result["checks"][0]["verdict"])
        self.assertEqual("error", result["checks"][0]["baseline_failure_kind"])
        self.assertEqual("FAIL", result["verdict"])

    def test_regression_guard_must_pass_on_baseline(self) -> None:
        good = self.check("import app\nassert app.greet() == 'hi'\n", expectation="green-before-green-after")
        self.assertEqual("admitted", admit([good], self.baseline)["checks"][0]["verdict"])
        bad = self.check("import app\nassert app.greet() == 'nope'\n", expectation="green-before-green-after", id="c2")
        self.assertEqual("rejected", admit([bad], self.baseline)["checks"][0]["verdict"])

    def test_check_without_requirement_ref_is_rejected(self) -> None:
        row = self.check("import app\nassert app.greet() == 'x'\n", requirement_ref="")
        self.assertEqual("rejected", admit([row], self.baseline)["checks"][0]["verdict"])

    def test_check_without_expectation_is_rejected(self) -> None:
        row = self.check("assert False\n")
        row.pop("expectation")
        self.assertEqual("rejected", admit([row], self.baseline)["checks"][0]["verdict"])

    def test_classify_failure_prefers_assertion_over_traceback_noise(self) -> None:
        self.assertEqual("assertion", classify_failure("Traceback (most recent call last):\nAssertionError: nope"))
        self.assertEqual("error", classify_failure("ModuleNotFoundError: No module named 'x'"))

    def test_requirement_coverage_reports_uncovered_requirements(self) -> None:
        ledger = {"requirements": [{"id": "REQ-1"}, {"id": "REQ-2"}]}
        coverage = requirement_coverage([{"requirement_ref": "REQ-1"}], ledger)
        self.assertFalse(coverage["complete"])
        self.assertEqual(["REQ-2"], coverage["uncovered_requirement_ids"])


class NecessityProbeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.baseline = root / "before"
        self.workspace = root / "after"
        self.baseline.mkdir()
        (self.baseline / "app.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def write_after(self, content: str) -> None:
        import shutil
        if self.workspace.exists():
            shutil.rmtree(self.workspace)
        shutil.copytree(self.baseline, self.workspace)
        (self.workspace / "app.py").write_text(content, encoding="utf-8")

    def probe_with(self, check_body: str) -> dict:
        script = self.workspace / "chk.py"
        script.write_text(check_body, encoding="utf-8")
        suite = suite_of([{"id": "c1", "kind": "acceptance", "command": [sys.executable, "chk.py"]}])
        return necessity_probe.probe(suite, self.baseline, self.workspace)

    def test_covered_change_is_necessary(self) -> None:
        self.write_after("def add(a, b):\n    return a + b\n\ndef mul(a, b):\n    return a * b\n")
        result = self.probe_with("import app\nassert app.mul(3, 4) == 12\n")
        self.assertTrue(result["earned"])
        self.assertEqual(1.0, result["necessity_ratio"])
        self.assertEqual(0, result["uncovered"])

    def test_untested_change_is_uncovered_and_not_earned(self) -> None:
        # `mul` is added but nothing tests it: reverting it reddens nothing.
        self.write_after("def add(a, b):\n    return a + b\n\ndef mul(a, b):\n    return a * b\n")
        result = self.probe_with("import app\nassert app.add(1, 2) == 3\n")
        self.assertFalse(result["earned"])
        self.assertEqual(1, result["uncovered"])
        self.assertIn("app.py", result["uncovered_hunks"][0]["path"])

    def test_untested_function_cannot_hide_in_a_tested_neighbours_hunk(self) -> None:
        # Found on a fresh-repo run: difflib merges adjacent additions into ONE
        # opcode. Reverting that hunk removes both functions, the tested one
        # fails, and the untested one is scored "necessary". Splitting inserts
        # at definition boundaries is what makes the probe honest.
        self.write_after(
            "def add(a, b):\n    return a + b\n\n\n"
            "def mul(a, b):\n    return a * b\n\n\n"
            "def untested(a):\n    return a - 1\n")
        result = self.probe_with("import app\nassert app.mul(3, 4) == 12\n")
        self.assertFalse(result["earned"], "an untested function must not be certified")
        self.assertEqual(1, result["uncovered"])
        self.assertIn("untested", result["uncovered_hunks"][0]["preview"])

    def test_comment_only_change_is_never_probed(self) -> None:
        self.write_after("def add(a, b):\n    # a helpful note\n    return a + b\n")
        result = self.probe_with("import app\nassert app.add(1, 2) == 3\n")
        self.assertEqual(0, result["hunks_substantive"])
        self.assertTrue(result["earned"])

    def test_import_only_hunk_is_not_substantive(self) -> None:
        self.assertFalse(necessity_probe.is_substantive(["import os", "from x import y", ""]))
        self.assertTrue(necessity_probe.is_substantive(["x = compute()"]))

    def test_hunks_are_enumerated_per_file(self) -> None:
        self.write_after("def add(a, b):\n    return a + b\n\ndef mul(a, b):\n    return a * b\n")
        hunks = necessity_probe.hunks_for(self.baseline, self.workspace, "app.py")
        self.assertTrue(hunks)
        self.assertTrue(all(h["path"] == "app.py" for h in hunks))

    def test_the_suite_own_scripts_are_never_probed(self) -> None:
        # A check script living inside the workspace is part of the measuring
        # instrument, not of the change. Probing it would ask "is this check
        # necessary for a check to pass" and would inflate `uncovered`.
        self.write_after("def add(a, b):\n    return a + b\n\ndef mul(a, b):\n    return a * b\n")
        (self.workspace / "chk.py").write_text("import app\nassert app.mul(2, 3) == 6\n", encoding="utf-8")
        suite = suite_of([{"id": "c1", "kind": "acceptance", "command": [sys.executable, "chk.py"]}])
        self.assertIn("chk.py", necessity_probe.suite_owned_paths(suite, self.workspace))
        result = necessity_probe.probe(suite, self.baseline, self.workspace)
        self.assertTrue(result["earned"])
        self.assertFalse(any(row["path"] == "chk.py" for row in result["hunks"]))


if __name__ == "__main__":
    unittest.main()
