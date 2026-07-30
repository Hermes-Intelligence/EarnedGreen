#!/usr/bin/env python3
"""Tests for diff_oracle derivation logic (zero provider calls, no node needed).

The pipeline's honesty rests on two mechanical properties: a predicate exists
ONLY where the behaviour actually changed, and a predicate that any other valid
implementation disagrees with dies without judgement. Both are pinned here on
synthetic streams before the pipeline ever touches real history.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import diff_oracle


class Derivation(unittest.TestCase):
    def test_no_change_derives_no_predicate(self) -> None:
        streams = {"a": ["x", "y"]}
        result = diff_oracle.derive(streams, streams, [])
        self.assertEqual(result["admitted"], [])

    def test_a_behaviour_change_yields_red_before_green_after_predicates(self) -> None:
        before = {"a": ["1", "1", "2"]}
        after = {"a": ["1", "2"]}
        result = diff_oracle.derive(before, after, [])
        self.assertTrue(result["admitted"])
        # every admitted predicate is, by construction, green on after and red on before
        for predicate in result["admitted"]:
            actual_after = diff_oracle.PROJECTIONS[predicate["projection"]](after["a"])
            actual_before = diff_oracle.PROJECTIONS[predicate["projection"]](before["a"])
            self.assertEqual(actual_after, predicate["expected"])
            self.assertNotEqual(actual_before, predicate["expected"])

    def test_a_valid_variant_kills_format_pinning_predicates(self) -> None:
        """THE filter: altformat separates with a middot where after uses a comma.
        Projections that see the separator's identity (seq, joined, charset...)
        must die; projections both valid implementations agree on (count here)
        survive. This is the over-constraint failure class, handled mechanically."""
        before = {"a": ["1", "1", "2", "3", "4"]}
        after = {"a": ["1,", "2,", "3"]}
        altformat = {"a": ["1·", "2·", "3"]}
        with_filter = diff_oracle.derive(before, after, [altformat])
        without_filter = diff_oracle.derive(before, after, [])
        self.assertLess(len(with_filter["admitted"]), len(without_filter["admitted"]))
        self.assertGreater(with_filter["rejected_format_pinning"], 0)
        surviving = {p["projection"] for p in with_filter["admitted"]}
        self.assertIn("count", surviving, "count (5 -> 3) is separator-agnostic and must survive")
        self.assertNotIn("joined", surviving, "joined text contains the separator glyph and must die")
        self.assertNotIn("seq", surviving)

    def test_driver_errors_are_reported_never_swallowed(self) -> None:
        before = {"a": {"__error__": "boom"}}
        after = {"a": ["x"]}
        result = diff_oracle.derive(before, after, [])
        self.assertEqual(result["admitted"], [])
        self.assertTrue(result["driver_errors"])


class Evaluation(unittest.TestCase):
    def test_evaluate_reddens_a_divergent_implementation(self) -> None:
        before = {"a": ["1", "1", "2"]}
        after = {"a": ["1", "2"]}
        predicates = diff_oracle.derive(before, after, [])["admitted"]
        solution_like_before = diff_oracle.evaluate(predicates, {"a": ["1", "1", "2"]})
        self.assertFalse(solution_like_before["green"])
        solution_like_after = diff_oracle.evaluate(predicates, {"a": ["1", "2"]})
        self.assertTrue(solution_like_after["green"])

    def test_evaluate_reports_driver_errors_as_errors_not_green(self) -> None:
        predicates = [{"id": "a::seq", "input_id": "a", "projection": "seq", "expected": ["x"]}]
        result = diff_oracle.evaluate(predicates, {"a": {"__error__": "crash"}})
        self.assertFalse(result["green"])
        self.assertTrue(result["errors"])


class Gen4Relational(unittest.TestCase):
    """The gen-4 mid-levels the era ladder located: partial credit that still
    separates. Pinned on synthetic streams before touching real material."""

    BEFORE = {"chart": ["text:Total 5", "text:legend"],
              "cites": ["text:[1][2][3]"],
              "guard": ["text:same", "line:0,0,1,1"]}
    AFTER = {"chart": ["rect:0,0,4,4", "line:1,1,2,2", "circle:2,2,1",
                       "text:Total 5", "text:legend"],
             "cites": ["text:[1]", "text:[2]", "text:[3]"],
             "guard": ["text:same", "line:0,0,1,1"]}

    def test_gained_kinds_admit_as_subset_requirement_and_reward_partial_work(self) -> None:
        result = diff_oracle.derive_relational(self.BEFORE, self.AFTER, [])
        chart = [p for p in result["admitted"] if p["id"] == "chart::kinds-gained"]
        self.assertEqual(len(chart), 1)
        self.assertEqual(chart[0]["expected"], ["circle", "line", "rect"])
        # a DIFFERENT valid chart implementation — extra kinds, other coords — passes
        superset = {"chart": ["rect:9,9,1,1", "line:5,5,6,6", "circle:0,0,3",
                              "path:legend-box", "text:Total 5"]}
        self.assertTrue(diff_oracle.evaluate(chart, superset)["green"])
        # partial work (rect only, no line/circle) stays red — separation kept
        partial = {"chart": ["rect:1,1,2,2", "text:Total 5"]}
        self.assertFalse(diff_oracle.evaluate(chart, partial)["green"])

    def test_count_direction_generalizes_the_v1_count_pattern(self) -> None:
        result = diff_oracle.derive_relational(self.BEFORE, self.AFTER, [])
        cites = [p for p in result["admitted"] if p["input_id"] == "cites"]
        self.assertEqual([p["id"] for p in cites], ["cites::count-text-increased"])
        # any implementation that split the run passes, regardless of exact count
        other_split = {"cites": ["text:[1]", "text:[2],[3]"]}
        self.assertTrue(diff_oracle.evaluate(cites, other_split)["green"])
        # an implementation still at the baseline count stays red
        untouched = {"cites": ["text:[1][2][3]"]}
        self.assertFalse(diff_oracle.evaluate(cites, untouched)["green"])

    def test_red_on_before_is_structural_and_guards_stay_silent(self) -> None:
        result = diff_oracle.derive_relational(self.BEFORE, self.AFTER, [])
        self.assertFalse([p for p in result["admitted"] if p["input_id"] == "guard"],
                         "unchanged inputs must yield no relational predicate")
        verdicts = diff_oracle.evaluate(result["admitted"], self.BEFORE)
        self.assertFalse(verdicts["green"])
        self.assertEqual(len(verdicts["red_predicate_ids"]), len(result["admitted"]),
                         "every relational predicate must be red on before by construction")

    def test_valid_variant_still_kills_implementation_pinning_relations(self) -> None:
        # the variant renders the chart with rect+line but NO circle: the gained-kinds
        # predicate would pin the reference's circle choice — it must die
        variant = {"chart": ["rect:0,0,4,4", "line:1,1,2,2", "text:Total 5", "text:legend"],
                   "cites": ["text:[1]", "text:[2]", "text:[3]"],
                   "guard": ["text:same", "line:0,0,1,1"]}
        result = diff_oracle.derive_relational(self.BEFORE, self.AFTER, [variant])
        self.assertFalse([p for p in result["admitted"] if p["id"] == "chart::kinds-gained"])
        self.assertGreater(result["rejected_by_variant"], 0)
        # the cites count direction is shared by the variant and survives
        self.assertTrue([p for p in result["admitted"] if p["input_id"] == "cites"])

    def test_driver_errors_reported_and_mixed_generations_evaluate_together(self) -> None:
        broken = {"chart": {"__error__": "boom"}, "cites": self.BEFORE["cites"],
                  "guard": self.BEFORE["guard"]}
        result = diff_oracle.derive_relational(broken, self.AFTER, [])
        self.assertTrue(result["driver_errors"])
        # a frozen pin list mixing exact and relational predicates evaluates in one pass
        mixed = [{"id": "cites::count", "input_id": "cites", "projection": "count", "expected": 3},
                 {"id": "cites::count-text-increased", "input_id": "cites",
                  "relation": "count-direction", "kind": "text", "baseline": 1,
                  "direction": "increased"}]
        verdict = diff_oracle.evaluate(mixed, {"cites": ["text:[1]", "text:[2]", "text:[3]"]})
        self.assertTrue(verdict["green"])
        unknown = diff_oracle.evaluate([{"id": "x", "input_id": "cites", "relation": "no-such"}],
                                       {"cites": ["text:a"]})
        self.assertFalse(unknown["green"])
        self.assertTrue(unknown["errors"], "an unknown relation must be an ERROR, never green")


class Corpus(unittest.TestCase):
    def test_corpus_is_deterministic_and_answer_free(self) -> None:
        one, two = diff_oracle.build_corpus(), diff_oracle.build_corpus()
        self.assertEqual(one, two, "the corpus must be pure: same inputs every run")
        self.assertGreaterEqual(len(one["inputs"]), 15)
        ids = [row["id"] for row in one["inputs"]]
        self.assertEqual(len(ids), len(set(ids)))
        # domain knowledge is allowed; ANSWER knowledge is not: no input may name
        # a convention or grading dimension
        rendered = str(one).lower()
        for banned in ("separat", "dedup", "convention", "cap-three", "citation-run"):
            self.assertNotIn(banned, rendered)


if __name__ == "__main__":
    unittest.main(verbosity=2)
