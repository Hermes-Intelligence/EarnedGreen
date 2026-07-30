#!/usr/bin/env python3
"""Tests for arm_validity (zero provider calls).

The regression these pin is not hypothetical: a campaign was halted at 4 of 28
approved calls because the loop arm's frozen suite was `[public-tests]` and could
not fail on anything the task is graded on. The fixture had been validated. The
metric had been validated. Nobody validated the ARM.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import arm_validity
from fixture_admission import Gate, local_fixture_dir

VEXTRUM = "vextrum-edition-rework-v1"
MEDI_NY = "medi-ny-parser-rework-v1"


class Probe(unittest.TestCase):
    def setUp(self) -> None:
        self.scratch = Path(tempfile.mkdtemp(prefix="awbp-arm-validity-"))
        self.addCleanup(shutil.rmtree, self.scratch, ignore_errors=True)

    def _gate(self, fixture_id: str) -> Gate:
        directory, contract = local_fixture_dir(fixture_id)
        if contract is None:
            self.skipTest(f"{fixture_id} not present")
        return Gate(directory)

    def test_an_empty_suite_is_vacuous(self) -> None:
        gate = self._gate(VEXTRUM)
        result = arm_validity.probe_suite({"schema_version": 1, "config": {}, "checks": []},
                                          gate, self.scratch / "empty")
        self.assertEqual(result["verdict"], "vacuous")
        self.assertIn("no behavioural check", result["reason"])

    def test_a_symbol_sweep_alone_is_vacuous(self) -> None:
        """A sweep asks whether the implementer inspected consumers. It says
        nothing about whether the suite can see the bug."""
        gate = self._gate(VEXTRUM)
        suite = {"schema_version": 1, "config": {},
                 "checks": [{"id": "symbol-sweep", "kind": "symbol-sweep", "authored_by": "harness"}]}
        self.assertEqual(arm_validity.probe_suite(suite, gate, self.scratch / "sweep")["verdict"], "vacuous")

    def test_the_real_defect_that_halted_the_campaign(self) -> None:
        """THE regression, pinned at the level it actually lives at.

        Vextrum's COMPILED suite is `[public-tests]`, green on the historical bug.
        Probing it directly still says so, and that is what must never be allowed
        to become a trial.
        """
        directory, contract = local_fixture_dir(VEXTRUM)
        if contract is None:
            self.skipTest("vextrum fixture not present")
        gate = Gate(directory)
        suite = {"schema_version": 1, "config": {},
                 "checks": [{"id": "public-tests", "kind": "acceptance", "authored_by": "harness",
                             "command": list(contract["public_test"])}]}
        result = arm_validity.probe_suite(suite, gate, self.scratch / "compiled")
        self.assertEqual(result["verdict"], "vacuous")
        self.assertTrue(result["green_on_before"],
                        "the compiled suite is green on the pre-change code: that IS the defect")

    def test_an_authoring_arm_defers_the_proof_and_says_so(self) -> None:
        """Vextrum's loop now authors its suite during the run, so there is
        nothing on disk to probe. The verdict must record WHERE the proof moved
        rather than quietly passing -- and the place it moves to must fail closed,
        which `tests/test_author_role.py::AuthorInto` is what actually pins."""
        result = arm_validity.validate(VEXTRUM, ["standard-loop"], self.scratch / "vextrum")
        self.assertEqual(result["verdict"], "PASS")
        arm = result["arms"][0]
        self.assertEqual(arm["verdict"], "authored-at-run-time")
        self.assertTrue(arm["authoring"]["enabled"])
        self.assertIn("check_admission", arm["reason"])

    def test_a_fixture_with_real_harness_checks_discriminates(self) -> None:
        """The tool must not simply fail everything: medi-ny's suite genuinely
        reddens on the historical bug and passes on the shipped fix."""
        result = arm_validity.validate(MEDI_NY, ["standard-loop"], self.scratch / "medi")
        self.assertEqual(result["verdict"], "PASS")
        arm = result["arms"][0]
        self.assertEqual(arm["verdict"], "discriminates")
        self.assertFalse(arm["green_on_before"])
        self.assertTrue(arm["green_on_after"])

    def test_control_arms_are_not_failed_for_holding_no_checks(self) -> None:
        """The gate and the frozen suite are what a control is DEFINED not to
        have. Failing it for that would be nonsense."""
        result = arm_validity.validate(VEXTRUM, ["vanilla", "vanilla-configured"], self.scratch / "controls")
        self.assertEqual(result["verdict"], "PASS")
        self.assertTrue(all(a["verdict"] == "not-applicable" for a in result["arms"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
