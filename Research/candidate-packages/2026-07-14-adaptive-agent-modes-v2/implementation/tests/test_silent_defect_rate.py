#!/usr/bin/env python3
"""Tests for silent_defect_rate (zero provider calls).

`Contract` takes the record shape FROM A REAL GRADED RUN on disk rather than from
a literal typed here: a fixture I invent and code I write agree with each other
while being wrong together, which has already cost this package two fatal bugs.
"""
from __future__ import annotations

import glob
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import silent_defect_rate as sdr

REPO = next(p for p in HERE.resolve().parents if (p / "Runtime/stable/manifest.json").exists())


def oracle(*passing: bool) -> dict:
    return {"passed": all(passing), "score": round(sum(passing) * 100 / len(passing)),
            "checks": [{"id": f"dim-{i}", "passed": p, "weight": 1} for i, p in enumerate(passing)]}


class VisibleVerdict(unittest.TestCase):
    def test_a_gated_arm_is_judged_by_its_gate(self) -> None:
        record = {"pre_submit_gate": {"verdict": "PASS", "completion_allowed": True},
                  "public_tests": {"passed": False}}
        self.assertEqual(sdr.visible_verdict(record), (True, "pre-submit-gate"))

    def test_a_bare_arm_is_judged_by_the_public_tests(self) -> None:
        """Judging a bare arm by a gate it never ran would flatter it."""
        record = {"public_tests": {"passed": True}}
        self.assertEqual(sdr.visible_verdict(record), (True, "public-tests"))

    def test_a_gate_that_passed_but_forbade_completion_is_not_done(self) -> None:
        record = {"pre_submit_gate": {"verdict": "PASS", "completion_allowed": False}}
        self.assertEqual(sdr.visible_verdict(record)[0], False)


class Compute(unittest.TestCase):
    def test_claimed_done_with_oracle_failures_is_the_silent_case(self) -> None:
        row = sdr.compute({"arm": "vanilla", "public_tests": {"passed": True},
                           "grader": oracle(True, False, False, True)})
        self.assertTrue(row["claimed_done"])
        self.assertEqual(row["silent_defects"], ["dim-1", "dim-2"])
        self.assertEqual(row["silent_defect_rate"], 0.5)

    def test_an_honest_red_is_not_a_silent_defect(self) -> None:
        """The environment exists to make failures loud. An arm that reported red
        has an honest failure, and counting it as silent would erase the
        distinction the whole metric is built on."""
        row = sdr.compute({"arm": "vanilla", "public_tests": {"passed": False},
                           "grader": oracle(False, False)})
        self.assertFalse(row["claimed_done"])
        self.assertEqual(row["silent_defects"], [])
        self.assertEqual(row["silent_defect_rate"], 0.0)
        self.assertIn("honest", row["note"])

    def test_a_clean_run_is_zero(self) -> None:
        row = sdr.compute({"arm": "loop", "pre_submit_gate": {"verdict": "PASS", "completion_allowed": True},
                           "grader": oracle(True, True, True)})
        self.assertEqual(row["silent_defect_rate"], 0.0)
        self.assertEqual(row["silent_defects"], [])

    def test_a_missing_oracle_is_undefined_not_zero(self) -> None:
        """Returning 0.0 for a crashed oracle reports the BEST possible result for
        the WORST possible evidence."""
        row = sdr.compute({"arm": "vanilla", "public_tests": {"passed": True}, "grader": {}})
        self.assertIsNone(row["silent_defect_rate"])
        self.assertIn("UNDEFINED", row["note"])


class Aggregate(unittest.TestCase):
    def test_per_arm_means_and_the_headline_count(self) -> None:
        rows = [
            sdr.compute({"arm": "vanilla", "public_tests": {"passed": True}, "grader": oracle(True, False)}),
            sdr.compute({"arm": "vanilla", "public_tests": {"passed": True}, "grader": oracle(False, False)}),
            sdr.compute({"arm": "loop", "pre_submit_gate": {"verdict": "PASS", "completion_allowed": True},
                         "grader": oracle(True, True)}),
        ]
        summary = sdr.aggregate(rows)
        self.assertEqual(summary["arms"]["vanilla"]["silent_defect_rate_mean"], 0.75)
        self.assertEqual(summary["arms"]["vanilla"]["claimed_done_with_silent_defects"], 2)
        self.assertEqual(summary["arms"]["loop"]["silent_defect_rate_mean"], 0.0)
        self.assertEqual(summary["arms"]["loop"]["claimed_done_with_silent_defects"], 0)

    def test_an_undefined_run_is_excluded_from_the_mean_and_reported(self) -> None:
        """Averaging over a broken oracle would launder it into the result."""
        rows = [
            sdr.compute({"arm": "a", "public_tests": {"passed": True}, "grader": oracle(True, False)}),
            sdr.compute({"arm": "a", "public_tests": {"passed": True}, "grader": {}}),
        ]
        summary = sdr.aggregate(rows)
        self.assertEqual(summary["arms"]["a"]["silent_defect_rate_mean"], 0.5)
        self.assertEqual(summary["arms"]["a"]["undefined_oracle_runs"], 1)


class Contract(unittest.TestCase):
    """Pin the record shape against a REAL graded run, not a literal I typed."""

    def test_real_run_records_are_readable(self) -> None:
        records = sorted(glob.glob(str(REPO / "Evals/runs/*/run-record.json")))
        if not records:
            self.skipTest("no graded runs on disk")
        checked = 0
        for path in records[:40]:
            record = json.loads(Path(path).read_text(encoding="utf-8-sig"))
            if not (record.get("grader") or {}).get("checks"):
                continue
            row = sdr.compute(record)
            self.assertIn(row["visible_signal"], {"pre-submit-gate", "public-tests"})
            self.assertIsInstance(row["oracle_dimensions"], int)
            self.assertTrue(row["silent_defect_rate"] is None or 0.0 <= row["silent_defect_rate"] <= 1.0)
            checked += 1
        self.assertGreater(checked, 0, "no real graded run exposed an oracle: the shape is unverified")


if __name__ == "__main__":
    unittest.main(verbosity=2)
