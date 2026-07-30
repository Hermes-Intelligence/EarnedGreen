#!/usr/bin/env python3
"""Tests for relation_oracle (synthetic streams, no node) and coverage_manifest.

relation_oracle's honesty rests on: violations at mining time become FINDINGS
(never silently pinned), honoured relations become pins that a divergent
implementation reddens, and the envelope is measured — the miner never demands
more than the code already does. The manifest's honesty rests on: an uncovered
dimension is NAMED, and a check claiming an undeclared dimension is a surfaced
bookkeeping defect, not a silent no-op.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import coverage_manifest
import relation_oracle


def fake_streams(overrides: dict | None = None) -> dict:
    """A well-behaved implementation's captured streams for the relation corpus."""
    corpus = relation_oracle.build_relation_corpus()
    streams = {}
    for item in corpus["inputs"]:
        edition = item["edition"]
        pieces = [edition["title"], edition["content_json"]["summary"]]
        for block in edition["content_json"]["blocks"]:
            pieces += [block["title"], block["prose"]]
        streams[item["id"]] = [p for p in pieces if p]
    streams.update(overrides or {})
    return streams


def patched_capture(per_call: list[dict]):
    """diff_oracle.capture is invoked twice per mine/evaluate; feed it in order."""
    calls = iter(per_call)
    return mock.patch.object(relation_oracle.diff_oracle, "capture",
                             side_effect=lambda *_a, **_k: next(calls))


class Mining(unittest.TestCase):
    def test_a_well_behaved_module_yields_pins_and_no_findings(self) -> None:
        streams = fake_streams()
        with patched_capture([streams, streams]):
            result = relation_oracle.mine(Path("ws"), Path("corpus"))
        self.assertEqual(result["findings"], [])
        kinds = {pin["kind"] for pin in result["pins"]}
        self.assertEqual(kinds, {"totality", "determinism", "co-variation", "sentinel"})

    def test_a_hardcoded_module_is_a_finding_not_a_pin(self) -> None:
        """Identical output for differing inputs = the mechanical definition of
        hardcode. It must surface NOW, as a finding — that is the whole answer
        to 'the code is broken and there is no diff'."""
        streams = fake_streams()
        streams["cov-summary-b"] = streams["cov-summary-a"]  # summary ignored
        with patched_capture([streams, streams]):
            result = relation_oracle.mine(Path("ws"), Path("corpus"))
        suspicions = [f for f in result["findings"] if f["kind"] == "co-variation"]
        self.assertTrue(suspicions and "hardcode" in suspicions[0]["suspicion"])
        # and the sentinel for the ignored field is missing too
        self.assertTrue(any(f["kind"] == "sentinel" for f in result["findings"]))

    def test_a_crash_is_a_totality_finding_never_a_silent_skip(self) -> None:
        streams = fake_streams({"edge-long": {"__error__": "RangeError: boom"}})
        with patched_capture([streams, streams]):
            result = relation_oracle.mine(Path("ws"), Path("corpus"))
        totality = [f for f in result["findings"] if f["kind"] == "totality"]
        self.assertEqual(len(totality), 1)
        self.assertIn("RangeError", totality[0]["suspicion"])

    def test_nondeterminism_is_found_by_the_second_run(self) -> None:
        first, second = fake_streams(), fake_streams()
        second["det-1"] = second["det-1"] + ["noise-42"]
        with patched_capture([first, second]):
            result = relation_oracle.mine(Path("ws"), Path("corpus"))
        self.assertTrue(any(f["kind"] == "determinism" for f in result["findings"]))


class Evaluation(unittest.TestCase):
    def test_pins_redden_on_a_divergent_implementation(self) -> None:
        good = fake_streams()
        with patched_capture([good, good]):
            pins = relation_oracle.mine(Path("ws"), Path("corpus"))["pins"]
        bad = fake_streams()
        bad["cov-title-b"] = bad["cov-title-a"]  # a later hardcode regression
        with patched_capture([bad, bad]):
            outcome = relation_oracle.evaluate(pins, Path("ws"), Path("corpus"))
        self.assertFalse(outcome["green"])
        self.assertTrue(any(pin_id.startswith("cov::") for pin_id in outcome["red_pin_ids"]))

    def test_pins_hold_green_on_another_correct_implementation(self) -> None:
        """Relations are implementation-agnostic: a DIFFERENT correct
        implementation (other formatting, same relations) stays green."""
        good = fake_streams()
        with patched_capture([good, good]):
            pins = relation_oracle.mine(Path("ws"), Path("corpus"))["pins"]
        # "different but correct" must actually BE correct: decorating pieces and
        # appending a footer changes the stream everywhere while preserving every
        # relation (sentinels stay contained, fields still co-vary, runs stay
        # deterministic). Uppercasing would NOT qualify — it destroys URLs, which
        # is precisely what the url sentinel exists to catch.
        other = {key: [f"| {piece}" for piece in value] + ["footer"] if isinstance(value, list) else value
                 for key, value in fake_streams().items()}
        with patched_capture([other, other]):
            outcome = relation_oracle.evaluate(pins, Path("ws"), Path("corpus"))
        self.assertTrue(outcome["green"],
                        "a correct-but-different implementation must not redden relation pins")


class DerivedCheckKind(unittest.TestCase):
    """The harness `derived` kind: layer-1/2 predicates as frozen suite checks."""

    def test_malformed_derived_check_fails_closed(self) -> None:
        import harness_checks
        failures = harness_checks._check_derived({"kind": "derived", "layer": "vibes"}, Path("."))
        self.assertTrue(failures and "must name layer" in failures[0]["reason"])

    def test_capture_command_pins_are_self_describing(self) -> None:
        """The generic form: pins name their own capture command (any language,
        any driver) and carry plain projection predicates. This is what lets a
        Python ETL fixture and a JS renderer share one check kind."""
        import json as json_module
        import tempfile
        import harness_checks
        with tempfile.TemporaryDirectory() as temp:
            pins_file = Path(temp) / "pins.json"
            pins_file.write_text(json_module.dumps({
                "capture_command": ["{python}", "-c",
                                    "import json; print(json.dumps({'s1': ['a', 'b']}))"],
                "predicates": [{"id": "s1::count", "input_id": "s1", "projection": "count", "expected": 2},
                               {"id": "s1::seq", "input_id": "s1", "projection": "seq", "expected": ["a", "b"]}],
            }), encoding="utf-8")
            check = {"kind": "derived", "layer": "diff", "pins": str(pins_file)}
            self.assertEqual(harness_checks._check_derived(check, Path(temp)), [])
            # and a diverging expectation reddens through the same path
            pins_file.write_text(pins_file.read_text(encoding="utf-8").replace('"expected": 2', '"expected": 3'),
                                 encoding="utf-8")
            failures = harness_checks._check_derived(check, Path(temp))
            self.assertTrue(any("s1::count" in f.get("predicate", "") for f in failures))

    def test_relation_layer_runs_against_a_workspace(self) -> None:
        """End-to-end with mocked captures: pins mined from a good stream must
        redden a hardcoded workspace through the harness-kind pathway."""
        import json as json_module
        import tempfile
        import harness_checks
        good = fake_streams()
        with patched_capture([good, good]):
            pins = relation_oracle.mine(Path("ws"), Path("corpus"))["pins"]
        with tempfile.TemporaryDirectory() as temp:
            pins_file = Path(temp) / "pins.json"
            pins_file.write_text(json_module.dumps({"pins": pins}), encoding="utf-8")
            corpus_file = Path(temp) / "corpus.json"
            corpus_file.write_text(json_module.dumps(relation_oracle.build_relation_corpus()),
                                   encoding="utf-8")
            check = {"kind": "derived", "layer": "relation",
                     "pins": str(pins_file), "corpus": str(corpus_file)}
            bad = fake_streams()
            bad["cov-title-b"] = bad["cov-title-a"]  # hardcode regression
            with patched_capture([bad, bad]):
                failures = harness_checks._check_derived(check, Path("ws"))
            self.assertTrue(any("cov::" in f.get("predicate", "") for f in failures))
            with patched_capture([good, good]):
                self.assertEqual(harness_checks._check_derived(check, Path("ws")), [])


class Manifest(unittest.TestCase):
    DIMS = [{"id": "citation-cap", "statement": "at most three"},
            {"id": "prose-preserved", "statement": "never delete content"},
            {"id": "long-prose-split", "statement": "split long paragraphs"}]

    def test_uncovered_dimensions_are_named_not_absorbed(self) -> None:
        checks = [{"id": "c1", "covers": ["citation-cap"], "provenance": "diff-derived"},
                  {"id": "c2", "covers": ["prose-preserved"], "provenance": "relation"}]
        manifest = coverage_manifest.build(self.DIMS, checks)
        self.assertEqual([row["id"] for row in manifest["unverified"]], ["long-prose-split"])
        rendered = coverage_manifest.render(manifest)
        self.assertIn("green does NOT mean these", rendered)
        self.assertIn("long-prose-split", rendered.split("UNVERIFIED")[1])

    def test_a_check_claiming_an_undeclared_dimension_is_a_surfaced_defect(self) -> None:
        checks = [{"id": "c1", "covers": ["no-such-dimension"], "provenance": "authored"}]
        manifest = coverage_manifest.build(self.DIMS, checks)
        self.assertEqual(manifest["dangling_claims"],
                         [{"check": "c1", "claims": "no-such-dimension"}])

    def test_unknown_provenance_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "provenance"):
            coverage_manifest.build(self.DIMS, [{"id": "c1", "covers": [], "provenance": "vibes"}])

    def test_provenance_is_visible_per_dimension(self) -> None:
        checks = [{"id": "c1", "covers": ["citation-cap"], "provenance": "diff-derived"},
                  {"id": "c2", "covers": ["citation-cap"], "provenance": "relation"}]
        manifest = coverage_manifest.build(self.DIMS, checks)
        row = next(r for r in manifest["verified"] if r["id"] == "citation-cap")
        self.assertEqual({entry["provenance"] for entry in row["checks"]},
                         {"diff-derived", "relation"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
