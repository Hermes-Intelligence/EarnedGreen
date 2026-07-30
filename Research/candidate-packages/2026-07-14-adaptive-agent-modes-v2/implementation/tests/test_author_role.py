#!/usr/bin/env python3
"""Tests for the AUTHOR role (zero provider calls).

The load-bearing one is `Shortfall`. `arm_validity` returns `authored-at-run-time`
for an authoring arm, which is a PASS -- it stops proving discrimination itself
and points at check_admission plus the runner's hard stop instead. If that hard
stop does not fire, the preflight is a rubber stamp and we are back to the defect
that halted a campaign at 4 of 28 approved calls, only now with a gate claiming
it was checked.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import author_role
import check_authoring

VEXTRUM = "vextrum-edition-rework-v1"
MEDI_NY = "medi-ny-parser-rework-v1"

# A baseline where `total()` forgets the discount. The check below reddens on it
# via an assertion, so it is admissible; nothing here needs a provider.
BASELINE_SOURCE = """\
def total(items, discount=0):
    return sum(items)
"""

GOOD_CHECK = """\
import os, sys
sys.path.insert(0, os.getcwd())
from cart import total
assert total([100], discount=10) == 90, f"discount ignored: {total([100], discount=10)}"
"""

VACUOUS_CHECK = """\
assert True
"""


class Scratch(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="awbp-author-role-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.baseline = self.root / "baseline"
        self.baseline.mkdir()
        (self.baseline / "cart.py").write_text(BASELINE_SOURCE, encoding="utf-8")
        (self.baseline / "task.md").write_text("Apply the discount in total().", encoding="utf-8")
        tests = self.baseline / "tests"
        tests.mkdir()
        (tests / "test_cart.py").write_text("def test_smoke():\n    assert True\n", encoding="utf-8")
        self.detected = {"schema_version": 1,
                         "test": {"command": ["python3", "-m", "unittest", "discover", "-s", "tests"],
                                  "runner": "unittest"},
                         "test_dir": "tests"}
        self.suite = {"schema_version": 1, "config": {},
                      "checks": [{"id": "public-tests", "kind": "acceptance", "authored_by": "harness",
                                  "command": ["python3", "-c", "pass"]}]}

    def _author_run(self, checks: list[dict], files: dict[str, str]) -> Path:
        """A returned author workspace, exactly as the adapter would hand it back."""
        run = self.root / f"author-{len(list(self.root.iterdir()))}"
        workspace = run / "workspace"
        workspace.mkdir(parents=True)
        shutil.copytree(self.baseline, workspace, dirs_exist_ok=True)
        for rel, content in files.items():
            target = workspace / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content.encode("utf-8"))
        (workspace / author_role.REPLY_FILE).write_text(
            json.dumps({"checks": checks}, indent=2), encoding="utf-8")
        return run


class Collect(Scratch):
    def test_the_script_content_is_read_from_the_workspace(self) -> None:
        """The author writes real files and RUNS them; it does not inline them in
        JSON. Reuniting the two is what lets one validator serve both paths."""
        run = self._author_run(
            [{"id": "discount-applied", "kind": "property", "script": "checks/check_discount.py",
              "requirement_ref": "REQ-1", "expectation": "red-before-green-after"}],
            {"checks/check_discount.py": GOOD_CHECK})
        proposal = json.loads(author_role.collect_proposal(run))
        self.assertEqual(proposal["files"]["checks/check_discount.py"], GOOD_CHECK)

    def test_a_declared_script_that_was_never_written_is_an_error(self) -> None:
        run = self._author_run(
            [{"id": "ghost", "kind": "property", "script": "checks/never_written.py",
              "requirement_ref": "REQ-1", "expectation": "red-before-green-after"}], {})
        with self.assertRaises(check_authoring.AuthoringError) as caught:
            author_role.collect_proposal(run)
        self.assertIn("did not write", str(caught.exception))

    def test_no_reply_file_is_an_error_not_an_empty_suite(self) -> None:
        run = self.root / "silent"
        (run / "workspace").mkdir(parents=True)
        with self.assertRaises(check_authoring.AuthoringError):
            author_role.collect_proposal(run)

    def test_a_traversing_script_path_never_reaches_the_filesystem(self) -> None:
        """`../../..` is untrusted model output, and it is joined to a real path."""
        run = self._author_run(
            [{"id": "escape", "kind": "property", "script": "../../../etc/passwd",
              "requirement_ref": "REQ-1", "expectation": "red-before-green-after"}], {})
        with self.assertRaises(check_authoring.AuthoringError):
            author_role.collect_proposal(run)


class AuthorInto(Scratch):
    def test_an_admitted_check_is_merged_and_the_suite_refrozen(self) -> None:
        run = self._author_run(
            [{"id": "discount-applied", "kind": "property", "script": "checks/check_discount.py",
              "requirement_ref": "REQ-1", "expectation": "red-before-green-after"}],
            {"checks/check_discount.py": GOOD_CHECK})
        reply = author_role.collect_proposal(run)
        merged, record = author_role.author_into(
            self.suite, lambda _p: reply, "brief", self.baseline,
            self.root / "scratch", self.detected)
        self.assertEqual([c["id"] for c in merged["checks"]], ["public-tests", "discount-applied"])
        self.assertEqual(record["checks"][0]["command"],
                         [sys.executable, "checks/check_discount.py"])

    def test_a_vacuous_check_is_rejected_and_the_trial_refused(self) -> None:
        """THE hard stop. A suite of vacuous checks must not become a trial."""
        run = self._author_run(
            [{"id": "always-true", "kind": "property", "script": "checks/check_nothing.py",
              "requirement_ref": "REQ-1", "expectation": "red-before-green-after"}],
            {"checks/check_nothing.py": VACUOUS_CHECK})
        reply = author_role.collect_proposal(run)
        with self.assertRaises(author_role.AuthoringShortfall) as caught:
            author_role.author_into(self.suite, lambda _p: reply, "brief", self.baseline,
                                    self.root / "scratch", self.detected)
        self.assertIn("no behavioural check", str(caught.exception))

    def test_an_author_that_returns_nothing_usable_refuses_the_trial(self) -> None:
        with self.assertRaises(author_role.AuthoringShortfall):
            author_role.author_into(self.suite, lambda _p: "I could not do this.", "brief",
                                    self.baseline, self.root / "scratch", self.detected)

    def test_the_authors_own_edits_never_reach_admission(self) -> None:
        """If the author implements the feature to make its check pass, its check
        is still judged on the code as it really is. The edit is discarded; the
        vacuous check it was hiding is not."""
        run = self._author_run(
            [{"id": "discount-applied", "kind": "property", "script": "checks/check_discount.py",
              "requirement_ref": "REQ-1", "expectation": "red-before-green-after"}],
            {"checks/check_discount.py": GOOD_CHECK})
        # The author "helpfully" fixes the code in its own workspace.
        (run / "workspace" / "cart.py").write_text(
            "def total(items, discount=0):\n    return sum(items) * (100 - discount) // 100\n",
            encoding="utf-8")
        reply = author_role.collect_proposal(run)
        merged, record = author_role.author_into(
            self.suite, lambda _p: reply, "brief", self.baseline,
            self.root / "scratch", self.detected)
        # Admission ran against the untouched baseline, where the check reddens.
        self.assertEqual(record["rounds"][0]["admitted"], 1)
        self.assertEqual(BASELINE_SOURCE, (self.baseline / "cart.py").read_text(encoding="utf-8"),
                         "admission must never mutate the baseline snapshot")

    def test_installed_check_bytes_match_the_pinned_sha(self) -> None:
        """On Windows, text mode would rewrite \\n as \\r\\n and every authored
        check would fail closed as 'modified after freeze'."""
        run = self._author_run(
            [{"id": "discount-applied", "kind": "property", "script": "checks/check_discount.py",
              "requirement_ref": "REQ-1", "expectation": "red-before-green-after"}],
            {"checks/check_discount.py": GOOD_CHECK})
        reply = author_role.collect_proposal(run)
        merged, record = author_role.author_into(
            self.suite, lambda _p: reply, "brief", self.baseline,
            self.root / "scratch", self.detected)
        workspace = self.root / "solution-workspace"
        shutil.copytree(self.baseline, workspace)
        author_role.install_checks(record["files"], workspace)
        import harness_checks
        authored = next(c for c in merged["checks"] if c["id"] == "discount-applied")
        problems = harness_checks._verify_check_files(authored, workspace)
        self.assertEqual(problems, [], "the pinned sha must match the bytes on disk")


class RuntimeDepsAndPristine(Scratch):
    """The 2026-07-19 defect: the admission baseline was the host-baseline
    SNAPSHOT, which strips node_modules -- so every authored check for a JS repo
    error-redded on import and the arm was refused for the harness's fault, not
    the author's. The baseline must be the pristine workspace, runtime included,
    and pristineness must be proven rather than assumed.
    """

    def test_admission_scratch_preserves_runtime_dependencies(self) -> None:
        (self.baseline / "node_modules" / "somelib").mkdir(parents=True)
        (self.baseline / "node_modules" / "somelib" / "index.js").write_text("x", encoding="utf-8")
        reply = json.dumps({
            "checks": [{"id": "discount-applied", "kind": "property", "script": "checks/check_discount.py",
                        "requirement_ref": "REQ-1", "expectation": "red-before-green-after"}],
            "files": {"checks/check_discount.py": GOOD_CHECK}})
        author_role.author_into(self.suite, lambda _p: reply, "brief", self.baseline,
                                self.root / "scratch", self.detected)
        self.assertTrue((self.root / "scratch" / "node_modules" / "somelib" / "index.js").is_file(),
                        "the admission scratch must carry the baseline's runtime, or every check "
                        "that imports the code under test dies on import instead of asserting")

    def test_verify_pristine_accepts_untouched_and_refuses_drift(self) -> None:
        import harness_checks
        record = harness_checks.snapshot_baseline(self.baseline, self.root / "snap")
        author_role.verify_pristine(self.baseline, record)  # untouched: no raise
        (self.baseline / "cart.py").write_text("def total(items, discount=0):\n    return 0\n",
                                               encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "no longer the pre-change state"):
            author_role.verify_pristine(self.baseline, record)


class SharedHelper(Scratch):
    """The exact defect the first live canary hit: an author factors setup into a
    shared helper module every check imports. Collecting only the declared scripts
    dropped the helper, so every check died on ModuleNotFoundError at admission
    (error-red, never assertion-red) and nothing was admitted -- a trial refused
    for a reason that was the delivery contract's fault, not the author's.
    """

    HELPER = "from cart import total as _total\n"
    CHECK_VIA_HELPER = """\
import os, sys
sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.join(os.getcwd(), "checks"))
from helper import _total
assert _total([100], discount=10) == 90, f"discount ignored: {_total([100], discount=10)}"
"""

    def test_a_check_that_imports_a_helper_is_admitted_installed_and_pinned(self) -> None:
        run = self._author_run(
            [{"id": "discount-applied", "kind": "property", "script": "checks/check_discount.py",
              "requirement_ref": "REQ-1", "expectation": "red-before-green-after"}],
            {"checks/check_discount.py": self.CHECK_VIA_HELPER,
             "checks/helper.py": self.HELPER})  # a helper, not itself a declared check
        proposal = json.loads(author_role.collect_proposal(run))
        self.assertIn("checks/helper.py", proposal["files"],
                      "the shared helper must be collected even though no check names it as its script")

        reply = json.dumps(proposal)
        merged, record = author_role.author_into(
            self.suite, lambda _p: reply, "brief", self.baseline,
            self.root / "scratch", self.detected)
        # It admits ONLY because the helper travelled to the admission workspace.
        self.assertIn("discount-applied", [c["id"] for c in merged["checks"]])
        self.assertIn("checks/helper.py", record["files"])

        # The helper is pinned into the check's integrity list and installs with it,
        # so the check does not break on import in the solution workspace.
        authored = next(c for c in merged["checks"] if c["id"] == "discount-applied")
        pinned = {row["path"] for row in authored["files"]}
        self.assertEqual(pinned, {"checks/check_discount.py", "checks/helper.py"})
        workspace = self.root / "solution-workspace"
        shutil.copytree(self.baseline, workspace)
        author_role.install_checks(record["files"], workspace)
        import harness_checks
        self.assertEqual(harness_checks._verify_check_files(authored, workspace), [],
                         "both the check and its helper must be present, unmodified, on disk")


class Policy(unittest.TestCase):
    def test_vextrum_must_author_because_it_declares_no_checks(self) -> None:
        policy = author_role.authoring_policy(VEXTRUM)
        self.assertTrue(policy["enabled"])
        self.assertEqual(policy["max_calls_per_trial"], 1)
        self.assertEqual(policy["declared_by"], [])

    def test_medi_ny_does_not_author_because_it_ships_its_own_checks(self) -> None:
        policy = author_role.authoring_policy(MEDI_NY)
        self.assertFalse(policy["enabled"])
        self.assertEqual(policy["max_calls_per_trial"], 0)
        self.assertIn("harness/harness-checks.json", policy["declared_by"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
