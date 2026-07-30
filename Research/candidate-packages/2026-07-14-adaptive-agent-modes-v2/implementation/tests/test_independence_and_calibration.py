"""Tests for the six repo-agnostic mechanisms earned by family-4.

Each test is named after the thing that actually went wrong, so a future reader
can see what the mechanism is FOR rather than what it does.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import coverage_manifest as cm                      # noqa: E402
from calibration_gate import CalibrationGate, require_calibration  # noqa: E402


DIMENSIONS = [
    {"id": "board-renders", "statement": "the board shows six stages"},
    {"id": "fits-viewport", "statement": "the board fits the screen at 1440px"},
    {"id": "claims-true", "statement": "every number is reproducible from the database"},
]


class TestOracleIndependence(unittest.TestCase):
    def test_family4_would_have_opened_at_zero_percent(self):
        """Family-4's instrument was entirely spec-derived and scored two builds
        near-identically while missing every defect the owner found by eye."""
        checks = [{"id": f"c{i}", "covers": ["board-renders"], "provenance": "spec"}
                  for i in range(16)]
        manifest = cm.build(DIMENSIONS, checks)
        self.assertEqual(manifest["independence"]["score"], 0.0)
        self.assertIn("agrees with itself", cm.render(manifest))

    def test_data_derived_checks_count_as_independent(self):
        """A number recomputed from the database cannot be authored into truth."""
        checks = [{"id": "c1", "covers": ["claims-true"], "provenance": "data"},
                  {"id": "c2", "covers": ["board-renders"], "provenance": "spec"}]
        manifest = cm.build(DIMENSIONS, checks)
        self.assertEqual(manifest["independence"]["score"], 0.5)
        self.assertEqual(manifest["independence"]["strongest_source"], "data")

    def test_host_derived_outranks_spec(self):
        """The eyebrow colour and the nav icon size were both readable from the
        repo; neither arm was pointed at them."""
        self.assertGreater(cm.PROVENANCE_RANK["host"], cm.PROVENANCE_RANK["spec"])
        self.assertIn("host", cm.INDEPENDENT_PROVENANCE)
        self.assertNotIn("spec", cm.INDEPENDENT_PROVENANCE)

    def test_authored_checks_rank_at_the_bottom(self):
        """Measured: agent-authored, gate-admitted checks bought zero lift."""
        self.assertEqual(cm.PROVENANCE_RANK["authored"], 1)
        self.assertNotIn("authored", cm.INDEPENDENT_PROVENANCE)

    def test_a_model_review_never_counts_toward_independence(self):
        checks = [{"id": "c1", "covers": ["board-renders"], "provenance": "reviewed-unverified"}]
        manifest = cm.build(DIMENSIONS, checks)
        self.assertEqual(manifest["independence"]["certifying_checks"], 0)
        self.assertEqual(manifest["independence"]["score"], 0.0)


class TestUncoveredLeadsTheReport(unittest.TestCase):
    def test_the_first_line_is_the_gap_not_the_green(self):
        """The overflow dimension WAS named unverified on family-4 and nobody read
        it, because the summary opened with green."""
        checks = [{"id": "c1", "covers": ["board-renders"], "provenance": "spec"}]
        report = cm.render(cm.build(DIMENSIONS, checks))
        first = report.splitlines()[0]
        self.assertTrue(first.startswith("NOT MECHANICALLY COVERED"), first)
        self.assertIn("2 behaviour(s)", first)
        self.assertLess(report.index("fits-viewport"), report.index("EARNED GREEN"))

    def test_full_coverage_still_says_so_first(self):
        checks = [{"id": f"c{i}", "covers": [d["id"]], "provenance": "data"}
                  for i, d in enumerate(DIMENSIONS)]
        report = cm.render(cm.build(DIMENSIONS, checks))
        self.assertTrue(report.splitlines()[0].startswith("NOT MECHANICALLY COVERED: none"))


class TestCalibrationGate(unittest.TestCase):
    def test_a_working_instrument_is_allowed_to_grade(self):
        verdict = CalibrationGate().check(good_score=0.94, hollow_score=0.10)
        self.assertTrue(verdict.may_grade)

    def test_refuses_when_every_arm_would_score_a_believable_zero(self):
        """The unset VITE_API_BASE_URL case: the app threw at load, so a real
        implementation scored the same as a fake — both near zero."""
        verdict = CalibrationGate().check(good_score=0.0, hollow_score=0.0)
        self.assertFalse(verdict.may_grade)
        self.assertIn("known to be correct", verdict.report())

    def test_refuses_when_the_instrument_passes_a_deliberate_fake(self):
        verdict = CalibrationGate().check(good_score=0.95, hollow_score=0.90)
        self.assertFalse(verdict.may_grade)
        self.assertIn("deliberate fake", verdict.report())

    def test_refuses_when_loose_bands_let_both_pass_without_separating(self):
        """Separation only bites under LOOSER bands — the default bands already
        force a 0.30 gap, so this is tested where it can actually fire."""
        gate = CalibrationGate(bands={"good": (0.50, 1.0), "hollow": (0.0, 0.55)})
        verdict = gate.check(good_score=0.55, hollow_score=0.50)
        self.assertFalse(verdict.may_grade)
        self.assertIn("apart", verdict.report())

    def test_default_bands_make_separation_unreachable_and_that_is_documented(self):
        """A check that can never fire under its own defaults must not be sold as
        a guarantee; this pins the arithmetic so a future band change is noticed."""
        gate = CalibrationGate()
        smallest_possible_gap = gate.bands["good"][0] - gate.bands["hollow"][1]
        self.assertGreaterEqual(smallest_possible_gap, gate.min_separation)

    def test_require_calibration_raises_rather_than_returning_a_number(self):
        with self.assertRaises(RuntimeError):
            require_calibration(good_score=0.2, hollow_score=0.1)

    def test_guard_scores_both_fixtures_through_the_callers_own_grader(self):
        seen = []

        def grade(fixture):
            seen.append(fixture)
            return 0.9 if fixture == "good" else 0.05

        verdict = CalibrationGate().guard(grade)
        self.assertEqual(seen, ["good", "hollow"])
        self.assertTrue(verdict.may_grade)

    def test_bands_are_configurable_and_required(self):
        with self.assertRaises(ValueError):
            CalibrationGate(bands={"good": (0.8, 1.0)})


if __name__ == "__main__":
    unittest.main(verbosity=2)
