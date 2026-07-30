#!/usr/bin/env python3
"""Tests for check authoring + adversarial review (zero provider calls).

Every subagent here is a recorded response. That is deliberate and permanent for
this layer: the value of these modules is in what they REFUSE to accept, and a
refusal is testable without spending anything. A live call proves the plumbing
works once; these tests prove the guards hold every time.
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

import check_admission
import check_adversary
import check_authoring
import harness_checks
import project_detect

# The SHAPE here must be project_detect's real output shape, not a convenient
# invention: `Contract.test_detected_shape_is_the_real_one` pins it against the
# producer. An earlier version of this file invented `{"test_command": [...]}`,
# every unit test agreed with it, and the whole authoring path was still broken
# end-to-end -- both sides of the contract were mine, so the tests proved nothing.
DETECTED = {"test": {"command": [sys.executable, "-m", "pytest", "-q"], "runner": "pytest"},
            "test_dir": "tests"}
LEDGER = {"requirements": [{"id": "REQ-1", "statement": "discount(total, pct) applies a percentage discount"}]}

BASELINE_CALC = "def total(items):\n    return sum(items)\n"

# A check that discriminates: on pre-change code `discount` is absent, and the
# ASSERTION is what fails, not the import.
GOOD_CHECK_SOURCE = '''\
def test_discount():
    from src import calc
    assert hasattr(calc, "discount"), "discount is not implemented"
    assert calc.discount(100, 10) == 90
'''

VACUOUS_CHECK_SOURCE = '''\
def test_nothing():
    assert True
'''

# Fails on the baseline only because the import explodes: goes green the moment
# an empty stub exists.
IMPORT_RED_SOURCE = '''\
from src.calc import discount


def test_discount_exists():
    assert discount is not None
'''


def proposal(script_source: str, check_id: str = "discount-applies-percentage",
             script: str = "checks/test_discount.py",
             expectation: str = "red-before-green-after") -> str:
    return json.dumps({
        "checks": [{"id": check_id, "kind": "acceptance", "script": script,
                    "requirement_ref": "REQ-1", "expectation": expectation,
                    "guidance": "src/calc.py has no discount yet"}],
        "files": {script: script_source},
    })


class Workspace(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="awbp-authoring-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.baseline = self.root / "baseline"
        (self.baseline / "src").mkdir(parents=True)
        (self.baseline / "src" / "__init__.py").write_text("", encoding="utf-8")
        (self.baseline / "src" / "calc.py").write_text(BASELINE_CALC, encoding="utf-8")
        self.scratch = self.root / "scratch"

    def candidate(self, calc_source: str) -> Path:
        """A workspace holding an implementation of the task."""
        target = self.root / "candidate"
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(self.baseline, target)
        (target / "src" / "calc.py").write_text(calc_source, encoding="utf-8")
        return target


class ParseProposal(unittest.TestCase):
    def test_accepts_fenced_json(self) -> None:
        parsed = check_authoring.parse_proposal("here you go\n```json\n" + proposal(GOOD_CHECK_SOURCE) + "\n```")
        self.assertEqual(parsed["checks"][0]["id"], "discount-applies-percentage")

    def test_rejects_empty_response(self) -> None:
        with self.assertRaises(check_authoring.AuthoringError):
            check_authoring.parse_proposal("   ")

    def test_rejects_prose_without_json(self) -> None:
        with self.assertRaises(check_authoring.AuthoringError):
            check_authoring.parse_proposal("I think we should test the discount function thoroughly.")

    def test_rejects_check_without_requirement_ref(self) -> None:
        body = json.loads(proposal(GOOD_CHECK_SOURCE))
        del body["checks"][0]["requirement_ref"]
        with self.assertRaises(check_authoring.AuthoringError):
            check_authoring.parse_proposal(json.dumps(body))

    def test_rejects_script_absent_from_files(self) -> None:
        body = json.loads(proposal(GOOD_CHECK_SOURCE))
        body["files"] = {"checks/other.py": "x = 1"}
        with self.assertRaises(check_authoring.AuthoringError):
            check_authoring.parse_proposal(json.dumps(body))

    def test_rejects_duplicate_ids(self) -> None:
        body = json.loads(proposal(GOOD_CHECK_SOURCE))
        body["checks"].append(dict(body["checks"][0]))
        with self.assertRaises(check_authoring.AuthoringError):
            check_authoring.parse_proposal(json.dumps(body))

    def test_rejects_unsupported_kind(self) -> None:
        body = json.loads(proposal(GOOD_CHECK_SOURCE))
        body["checks"][0]["kind"] = "vibes"
        with self.assertRaises(check_authoring.AuthoringError):
            check_authoring.parse_proposal(json.dumps(body))


class ProposalPathSafety(unittest.TestCase):
    """The harness EXECUTES these files, so a model-supplied path is untrusted
    input. A traversal here would let a proposal overwrite the implementation it
    is supposed to be judging."""

    def _reject(self, rel: str) -> None:
        body = json.loads(proposal(GOOD_CHECK_SOURCE))
        body["checks"][0]["script"] = rel
        body["files"] = {rel: "x = 1"}
        with self.assertRaises(check_authoring.AuthoringError):
            check_authoring.parse_proposal(json.dumps(body))

    def test_rejects_traversal(self) -> None:
        self._reject("checks/../src/calc.py")

    def test_rejects_absolute_path(self) -> None:
        self._reject("C:/Windows/System32/evil.py")

    def test_rejects_path_outside_checks_root(self) -> None:
        self._reject("src/calc.py")

    def test_rejects_backslash_path(self) -> None:
        self._reject("checks\\test_x.py")

    def test_materialize_revalidates_paths(self) -> None:
        """parse_proposal is not the only door: a proposal can be loaded off disk,
        and a guard that runs on one code path is not a guard."""
        with tempfile.TemporaryDirectory() as tmp:
            evil = {"files": {"checks/../../escape.py": "x = 1"}}
            with self.assertRaises(check_authoring.AuthoringError):
                check_authoring.materialize(evil, Path(tmp))


class Admission(Workspace):
    def test_admits_a_discriminating_check(self) -> None:
        result = check_authoring.author(
            "brief", lambda _p: proposal(GOOD_CHECK_SOURCE),
            self.baseline, self.scratch, DETECTED, LEDGER)
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(result["author_calls"], 1)
        self.assertEqual(len(result["checks"]), 1)
        self.assertTrue(result["requirement_coverage"]["complete"])

    def test_rejects_a_vacuous_check(self) -> None:
        result = check_authoring.author(
            "brief", lambda _p: proposal(VACUOUS_CHECK_SOURCE),
            self.baseline, self.scratch, DETECTED, LEDGER, max_calls=1)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertEqual(result["checks"], [])
        self.assertIn("discount-applies-percentage", result["rounds"][0]["rejected"])

    def test_import_error_red_is_suspicious_not_admitted(self) -> None:
        """The subtlety the whole gate rests on: an ImportError red goes green
        the moment an empty stub exists, so it is not evidence of anything."""
        result = check_authoring.author(
            "brief", lambda _p: proposal(IMPORT_RED_SOURCE),
            self.baseline, self.scratch, DETECTED, LEDGER, max_calls=1)
        self.assertEqual(result["checks"], [])
        self.assertIn("discount-applies-percentage", result["rounds"][0]["suspicious"])

    def test_reauthors_once_after_rejection(self) -> None:
        responses = [proposal(VACUOUS_CHECK_SOURCE), proposal(GOOD_CHECK_SOURCE)]
        seen: list[str] = []

        def responder(prompt: str) -> str:
            seen.append(prompt)
            return responses[len(seen) - 1]

        result = check_authoring.author("brief", responder, self.baseline, self.scratch, DETECTED, LEDGER)
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(result["author_calls"], 2)
        self.assertIn("VACUOUS", seen[1])

    def test_call_cap_is_enforced(self) -> None:
        calls = {"n": 0}

        def responder(_prompt: str) -> str:
            calls["n"] += 1
            return proposal(VACUOUS_CHECK_SOURCE)

        check_authoring.author("brief", responder, self.baseline, self.scratch, DETECTED, LEDGER)
        self.assertEqual(calls["n"], check_authoring.MAX_AUTHOR_CALLS)

    def test_malformed_response_never_yields_a_suite(self) -> None:
        result = check_authoring.author("brief", lambda _p: "sorry, I can't do that",
                                        self.baseline, self.scratch, DETECTED, LEDGER)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertIn("error", result["rounds"][0])

    def test_uncovered_requirement_fails_the_verdict(self) -> None:
        ledger = {"requirements": LEDGER["requirements"] + [{"id": "REQ-2", "statement": "rejects a negative pct"}]}
        result = check_authoring.author("brief", lambda _p: proposal(GOOD_CHECK_SOURCE),
                                        self.baseline, self.scratch, DETECTED, ledger, max_calls=1)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertEqual(result["requirement_coverage"]["uncovered_requirement_ids"], ["REQ-2"])


class Compilation(Workspace):
    def test_suite_uses_the_detected_runner(self) -> None:
        """The already-shipped defect this guards: a hardcoded runner the repo
        does not use finds no tests, exits 0, and is green forever."""
        result = check_authoring.author("brief", lambda _p: proposal(GOOD_CHECK_SOURCE),
                                        self.baseline, self.scratch, DETECTED, LEDGER)
        suite = check_authoring.to_suite(result)
        command = suite["checks"][0]["command"]
        self.assertIn("pytest", command)
        self.assertIn("checks/test_discount.py", command)

    def test_missing_runner_is_an_error_not_a_green_suite(self) -> None:
        with self.assertRaises(check_authoring.AuthoringError):
            check_authoring.runnable({"script": "checks/test_discount.py"}, {"test": {"command": []}})


class Contract(Workspace):
    """Pin the producer/consumer contract against the PRODUCER.

    Unit tests that assert against a hand-written fixture of someone else's
    output only prove the fixture and the code agree. When both are written by
    the same person, they agree while being wrong together -- which is exactly
    what happened here, and only a real end-to-end run caught it.
    """

    def test_detected_shape_is_the_real_one(self) -> None:
        (self.baseline / "pyproject.toml").write_text(
            "[tool.pytest.ini_options]\ntestpaths = [\"tests\"]\n", encoding="utf-8")
        (self.baseline / "tests").mkdir(exist_ok=True)
        detected = project_detect.detect(self.baseline)
        self.assertTrue(project_detect.test_command(detected),
                        "project_detect.detect() must expose a test command through the accessor")
        # The accessor is the only contract; reading the dict directly is what broke.
        compiled = check_authoring.runnable({"script": "checks/test_x.py"}, detected)
        self.assertIn("checks/test_x.py", compiled["command"])

    def test_the_DETECTED_fixture_matches_what_the_producer_emits(self) -> None:
        """The same trap, one field deeper. `check_command` reads `runner`, and
        this file's DETECTED fixture did not have one -- so the fixture and the
        code would have agreed on `python3 <pytest file>`: a command that defines
        a test, runs nothing, and exits 0. Pin every key the consumers read
        against the producer, not against my memory of it."""
        (self.baseline / "pyproject.toml").write_text(
            "[tool.pytest.ini_options]\ntestpaths = [\"tests\"]\n", encoding="utf-8")
        real = project_detect.detect(self.baseline)["test"]
        for key in ("command", "runner"):
            self.assertIn(key, real, f"project_detect stopped emitting {key!r}")
            self.assertIn(key, DETECTED["test"], f"the DETECTED fixture is missing {key!r}")
        self.assertEqual(DETECTED["test"]["runner"], real["runner"])

    def test_an_unknown_python_runner_is_refused_not_guessed(self) -> None:
        with self.assertRaises(project_detect.UnrunnableCheck):
            project_detect.check_command({"test": {"command": ["make", "test"], "runner": "make"}},
                                         "checks/test_x.py")

    def test_a_node_check_is_not_appended_to_the_repos_own_test_files(self) -> None:
        """`test_command + [script]` would run the repo's suite alongside the
        check and make the check's verdict depend on it."""
        detected = {"test": {"command": ["node", "--test", "tests/public.test.js"],
                             "runner": "node--test"}}
        self.assertEqual(project_detect.check_command(detected, "checks/citations.test.mjs"),
                         ["node", "--test", "checks/citations.test.mjs"])
        self.assertEqual(project_detect.check_command(detected, "checks/citations.mjs"),
                         ["node", "checks/citations.mjs"])

    def test_accessor_on_a_runner_less_project_is_empty_not_a_crash(self) -> None:
        detected = project_detect.detect(self.baseline)
        self.assertEqual(project_detect.test_command({}), [])
        self.assertIsInstance(project_detect.test_command(detected), list)

    def test_suite_owned_paths_ignores_the_absolute_interpreter(self) -> None:
        """`workspace / <absolute>` returns the absolute path back, so a command
        pinning an absolute interpreter -- which is how the detected runner is
        pinned on Windows -- claimed python.exe as a check script."""
        import necessity_probe

        suite = {"checks": [{"id": "c", "kind": "acceptance",
                             "command": [sys.executable, "-m", "pytest", "checks/test_discount.py"]}]}
        (self.baseline / "checks").mkdir(exist_ok=True)
        (self.baseline / "checks" / "test_discount.py").write_text("", encoding="utf-8")
        owned = necessity_probe.suite_owned_paths(suite, self.baseline)
        self.assertEqual(owned, {"checks/test_discount.py"})
        self.assertFalse([path for path in owned if Path(path).is_absolute()])

    def test_freeze_pins_script_bytes(self) -> None:
        result = check_authoring.author("brief", lambda _p: proposal(GOOD_CHECK_SOURCE),
                                        self.baseline, self.scratch, DETECTED, LEDGER)
        suite = check_authoring.to_suite(result)
        workspace = self.candidate(BASELINE_CALC + "\n\ndef discount(total, pct):\n    return total * (100 - pct) / 100\n")
        check_authoring.materialize(result, workspace)
        self.assertEqual(harness_checks.run_suite(suite, workspace)["green"], True)
        # Weaken the check after the freeze: it must fail closed.
        (workspace / "checks" / "test_discount.py").write_text("def test_discount():\n    assert True\n",
                                                               encoding="utf-8")
        report = harness_checks.run_suite(suite, workspace)
        self.assertFalse(report["green"])
        self.assertIn("modified after freeze",
                      json.dumps(report["checks"][0]["failures"]))

    def test_suite_is_frozen_with_a_digest(self) -> None:
        result = check_authoring.author("brief", lambda _p: proposal(GOOD_CHECK_SOURCE),
                                        self.baseline, self.scratch, DETECTED, LEDGER)
        suite = check_authoring.to_suite(result)
        self.assertEqual(suite["harness_freeze_sha256"], harness_checks.harness_freeze_sha256(suite))
        self.assertEqual(suite["checks"][0]["authored_by"], "harness")


# --- adversary ---------------------------------------------------------------

CORRECT_CALC = BASELINE_CALC + '''

def discount(total, pct):
    if pct < 0 or pct > 100:
        raise ValueError("pct out of range")
    return total * (100 - pct) / 100
'''

# Passes `discount(100, 10) == 90` and nothing else: the classic hard-code.
CHEATING_CALC = BASELINE_CALC + '''

def discount(total, pct):
    return 90
'''

WITNESS_SOURCE = '''\
from src import calc

print(calc.discount(200, 50))
'''

NONDETERMINISTIC_WITNESS = '''\
import random

print(random.random())
'''

BROKEN_WITNESS = '''\
raise SystemExit(3)
'''


def attack_response(files: dict[str, str], witness_source: str = WITNESS_SOURCE) -> str:
    return json.dumps({
        "files": files,
        "witness": {"witness/probe.py": witness_source},
        "witness_command": ["python3", "witness/probe.py"],
        "violated_requirement": "REQ-1",
        "explanation": "hard-codes the single value the check asserts",
    })


class AdversaryParsing(Workspace):
    def setUp(self) -> None:
        super().setUp()
        self.suite = {"schema_version": 1, "config": {}, "checks": [
            {"id": "discount-applies-percentage", "kind": "acceptance", "script": "checks/test_discount.py",
             "command": project_detect.test_command(DETECTED) + ["checks/test_discount.py"],
             "authored_by": "harness"}]}

    def test_rejects_attack_without_a_witness(self) -> None:
        body = json.loads(attack_response({"src/calc.py": CHEATING_CALC}))
        del body["witness"]
        with self.assertRaises(check_adversary.AdversaryError):
            check_adversary.parse_attack(json.dumps(body), self.suite, self.baseline)

    def test_rejects_attack_that_edits_the_frozen_checks(self) -> None:
        """Defeating the suite by rewriting the suite is not an attack; it voids
        the exercise."""
        body = json.loads(attack_response({"checks/test_discount.py": "def test_discount():\n    assert True\n"}))
        with self.assertRaises(check_adversary.AdversaryError):
            check_adversary.parse_attack(json.dumps(body), self.suite, self.baseline)

    def test_rejects_witness_outside_witness_root(self) -> None:
        body = json.loads(attack_response({"src/calc.py": CHEATING_CALC}))
        body["witness"] = {"src/probe.py": WITNESS_SOURCE}
        with self.assertRaises(check_adversary.AdversaryError):
            check_adversary.parse_attack(json.dumps(body), self.suite, self.baseline)

    def test_rejects_traversal_in_implementation_path(self) -> None:
        body = json.loads(attack_response({"../escape.py": "x = 1"}))
        with self.assertRaises(check_adversary.AdversaryError):
            check_adversary.parse_attack(json.dumps(body), self.suite, self.baseline)


class AdversaryReview(Workspace):
    def setUp(self) -> None:
        super().setUp()
        authored = check_authoring.author("brief", lambda _p: proposal(GOOD_CHECK_SOURCE),
                                          self.baseline, self.scratch, DETECTED, LEDGER)
        self.suite = check_authoring.to_suite(authored)
        self.authored = authored
        self.attack_scratch = self.root / "attack-scratch"

    def _candidate_with_checks(self, calc_source: str) -> Path:
        workspace = self.candidate(calc_source)
        check_authoring.materialize(self.authored, workspace)
        return workspace

    def _review(self, response: str, calc_source: str = CORRECT_CALC) -> dict:
        candidate = self._candidate_with_checks(calc_source)
        # The baseline is passed EXACTLY as production has it: snapshotted before
        # the checks were authored, so it does not contain them. An earlier
        # version of this helper hand-copied the checks in, which hid the fact
        # that `review` never installed them -- every attack died on "check script
        # missing" and the adversary could not win by construction.
        parsed = check_adversary.parse_attack(response, self.suite, candidate)
        return check_adversary.review(parsed, self.suite, self.baseline, candidate, self.attack_scratch)

    def test_checks_held_when_the_attack_fails_the_suite(self) -> None:
        result = self._review(attack_response({"src/calc.py": BASELINE_CALC}))
        self.assertEqual(result["verdict"], "checks-held")
        self.assertFalse(result["suite_green_on_attack"])

    def test_suite_defeated_when_witness_diverges(self) -> None:
        """The headline: the suite is green on two implementations that provably
        behave differently, so it cannot tell them apart."""
        result = self._review(attack_response({"src/calc.py": CHEATING_CALC}))
        self.assertTrue(result["suite_green_on_attack"])
        self.assertTrue(result["witness_diverges"])
        self.assertEqual(result["verdict"], "suite-defeated")
        self.assertIn("100.0", result["witness_candidate_tail"])
        self.assertIn("90", result["witness_attack_tail"])

    def test_no_divergence_when_the_attack_is_equivalent(self) -> None:
        equivalent = BASELINE_CALC + "\n\ndef discount(total, pct):\n    return total - total * pct / 100\n"
        result = self._review(attack_response({"src/calc.py": equivalent}))
        self.assertTrue(result["suite_green_on_attack"])
        self.assertFalse(result["witness_diverges"])
        self.assertEqual(result["verdict"], "no-divergence")

    def test_nondeterministic_witness_is_inconclusive(self) -> None:
        """A witness that disagrees with itself would report noise as a hole."""
        result = self._review(attack_response({"src/calc.py": CHEATING_CALC}, NONDETERMINISTIC_WITNESS))
        self.assertEqual(result["verdict"], "inconclusive")
        self.assertIn("disagrees with itself", result["reason"])

    def test_broken_witness_is_inconclusive_not_a_win(self) -> None:
        result = self._review(attack_response({"src/calc.py": CHEATING_CALC}, BROKEN_WITNESS))
        self.assertEqual(result["verdict"], "inconclusive")

    def test_adversary_can_win_at_all(self) -> None:
        """The bug this pins was fatal and silent: the baseline snapshot predates
        authoring, so the frozen check scripts were absent from the attack
        workspace. Every attack died on 'check script missing', the adversary
        could never win by construction, and the harness reported "your checks
        are strong" 100% of the time. A mechanism that always returns comfort is
        worse than none, because it gets believed."""
        result = self._review(attack_response({"src/calc.py": CHEATING_CALC}))
        self.assertNotEqual(result["verdict"], "checks-held")
        self.assertTrue(result["suite_green_on_attack"])

    def test_symbol_sweep_is_not_run_against_an_attack(self) -> None:
        """A symbol sweep asks whether the implementer inspected its consumers.
        Against a hypothetical implementation nobody wrote, it fails for free and
        turns every result into 'checks held'."""
        suite = dict(self.suite, checks=self.suite["checks"] + [
            {"id": "sweep", "kind": "symbol-sweep", "authored_by": "harness"}])
        self.assertNotIn("sweep", [c["id"] for c in check_adversary.attackable(suite)["checks"]])

    def test_scratch_inside_the_workspace_does_not_recurse(self) -> None:
        """The scratch dir lives in .agentic/, i.e. inside the workspace: an
        unfiltered copytree copies the destination into itself until Windows'
        path limit stops it."""
        candidate = self._candidate_with_checks(CORRECT_CALC)
        inside = candidate / ".agentic" / "scratch"
        result = check_adversary.review(
            check_adversary.parse_attack(attack_response({"src/calc.py": CHEATING_CALC}), self.suite, candidate),
            self.suite, self.baseline, candidate, inside)
        self.assertEqual(result["verdict"], "suite-defeated")

    def test_unusable_response_is_inconclusive_not_checks_held(self) -> None:
        """An attack we failed to run is not an attack the checks defeated."""
        candidate = self._candidate_with_checks(CORRECT_CALC)
        result = check_adversary.attack("brief", lambda _p: "no thanks", self.suite,
                                        self.baseline, candidate, self.attack_scratch)
        self.assertEqual(result["verdict"], "inconclusive")


class Briefs(Workspace):
    def test_author_brief_states_the_falsification_rule(self) -> None:
        brief = check_authoring.build_brief("Add a discount function", self.baseline, LEDGER, DETECTED)
        self.assertIn("MUST FAIL now", brief)
        self.assertIn("REQ-1", brief)
        self.assertIn("ImportError", brief)

    def test_author_brief_lists_only_uncovered_requirements(self) -> None:
        ledger = {"requirements": [{"id": "REQ-1", "statement": "a"}, {"id": "REQ-2", "statement": "b"}]}
        existing = {"checks": [{"requirement_ref": "REQ-1"}]}
        brief = check_authoring.build_brief("t", self.baseline, ledger, DETECTED, existing_suite=existing)
        self.assertNotIn("REQ-1:", brief)
        self.assertIn("REQ-2:", brief)

    def test_adversary_brief_demands_a_witness(self) -> None:
        suite = {"checks": [{"id": "c1", "kind": "acceptance", "requirement_ref": "REQ-1"}]}
        brief = check_adversary.build_brief("Add a discount function", suite,
                                            {"checks/test_discount.py": GOOD_CHECK_SOURCE},
                                            {"src/calc.py": BASELINE_CALC})
        self.assertIn("WITNESS", brief)
        self.assertIn("deterministic", brief)
        self.assertIn("src/calc.py", brief)

    def test_adversary_brief_carries_current_file_content(self) -> None:
        """Observed live: given only filenames, the adversary rewrote the file
        from scratch, dropped an unrelated function, and died on an existing
        test. The harness then said "checks held" -- true of that attack, and a
        false impression of a strong suite."""
        suite = {"checks": [{"id": "c1", "kind": "acceptance", "requirement_ref": "REQ-1"}]}
        brief = check_adversary.build_brief("Add a discount function", suite, {},
                                            {"src/calc.py": BASELINE_CALC})
        self.assertIn("def total(items)", brief)
        self.assertIn("Keep everything you are not attacking", brief)


if __name__ == "__main__":
    unittest.main(verbosity=2)
