#!/usr/bin/env python3
"""Tests for notes_bank — the institutional learning loop (zero provider calls).

The bank's one enemy is rot: vague, unfalsifiable,永-provisional advice piling
up until agents skim past all of it. Every test here defends some part of the
anti-rot contract: validation at write time, routing instead of broadcast,
retirement on measured non-transfer, and capture that refuses to invent prose.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import author_role
import notes_bank
from notes_bank import NoteError


def note(**overrides):
    base = {
        "id": "test-note",
        "error_class": "weak-observable",
        "audience": ["check-author"],
        "applies_when": {"tags": ["rendering"]},
        "lesson": "assert on emitted content, not geometry",
        "how_to_apply": "read what the code emitted",
        "provenance": {"observed_in": ["run-1"], "observed_at": "2026-07-17"},
        "verification": {"status": "provisional", "records": []},
        "retire_when": "a measured transfer test shows non-transfer",
    }
    base.update(overrides)
    return base


class Validation(unittest.TestCase):
    def test_a_note_without_a_death_condition_is_rejected(self) -> None:
        """A note that cannot say how it would die is superstition."""
        with self.assertRaisesRegex(NoteError, "superstition"):
            notes_bank.validate_note(note(retire_when="  "))

    def test_measured_status_without_records_is_rejected(self) -> None:
        """An unrecorded measurement is a claim, and claims are provisional."""
        with self.assertRaisesRegex(NoteError, "unrecorded measurement"):
            notes_bank.validate_note(note(verification={"status": "measured", "records": []}))

    def test_provenance_must_name_what_was_actually_observed(self) -> None:
        with self.assertRaisesRegex(NoteError, "guess wearing a badge"):
            notes_bank.validate_note(note(provenance={"observed_at": "2026-07-17"}))

    def test_unknown_audience_is_rejected(self) -> None:
        with self.assertRaisesRegex(NoteError, "unknown audience"):
            notes_bank.validate_note(note(audience=["wizard"]))


class Routing(unittest.TestCase):
    def bank(self, *rows):
        return {"schema_version": 1, "notes": list(rows)}

    def test_audience_and_tag_overlap_route_the_note(self) -> None:
        bank = self.bank(note())
        self.assertEqual(len(notes_bank.relevant_notes(bank, "check-author", {"rendering", "js"})), 1)
        self.assertEqual(notes_bank.relevant_notes(bank, "implementer", {"rendering"}), [])
        self.assertEqual(notes_bank.relevant_notes(bank, "check-author", {"database"}), [])

    def test_a_note_with_no_tags_routes_to_every_context(self) -> None:
        bank = self.bank(note(id="untagged", applies_when={"tags": []}))
        self.assertEqual(len(notes_bank.relevant_notes(bank, "check-author", {"anything"})), 1)

    def test_retired_notes_never_route(self) -> None:
        """That is what retirement MEANS."""
        bank = self.bank(note(verification={"status": "retired", "records": []}))
        self.assertEqual(notes_bank.relevant_notes(bank, "check-author", {"rendering"}), [])

    def test_render_shows_status_and_action(self) -> None:
        text = notes_bank.render_for_brief([note()])
        self.assertIn("(provisional)", text)
        self.assertIn("How to apply:", text)
        self.assertIn("weak-observable", text)
        self.assertEqual(notes_bank.render_for_brief([]), "")


class Measurement(unittest.TestCase):
    def test_transfer_upgrades_and_non_transfer_retires(self) -> None:
        """The bank applies earned-green to itself: a lesson that measurably does
        not change behaviour is exactly the rot it exists to refuse."""
        bank = {"schema_version": 1, "notes": [note()]}
        notes_bank.record_measurement(bank, "test-note", {"transferred": True, "evidence": "e1"})
        self.assertEqual(bank["notes"][0]["verification"]["status"], "measured")
        notes_bank.record_measurement(bank, "test-note", {"transferred": False, "evidence": "e2"})
        self.assertEqual(bank["notes"][0]["verification"]["status"], "retired")
        self.assertIn("non-transfer", bank["notes"][0]["verification"]["retired_reason"])

    def test_a_measurement_must_carry_its_evidence(self) -> None:
        bank = {"schema_version": 1, "notes": [note()]}
        with self.assertRaises(NoteError):
            notes_bank.record_measurement(bank, "test-note", {"transferred": True})


class Capture(unittest.TestCase):
    def test_failure_then_recovery_becomes_a_draft_not_prose(self) -> None:
        """Capture guarantees no observed error is forgotten; it must NOT
        pretend to understand the failure by generating the lesson itself."""
        campaign = {"runs": [{
            "run_id": "r1", "arm": "standard-loop",
            "iterations": [
                {"iteration": 1, "green": False, "failing_check_ids": ["citation-cap"]},
                {"iteration": 2, "green": True, "failing_check_ids": []},
            ]}]}
        drafts = notes_bank.draft_from_campaign(campaign)
        self.assertEqual(len(drafts), 1)
        self.assertTrue(drafts[0]["provenance"]["recovered_later"])
        # every field a MIND must fill is marked, so a draft cannot silently
        # pose as a finished lesson in review
        self.assertIn("TODO", drafts[0]["lesson"])
        self.assertIn("TODO", drafts[0]["error_class"])
        self.assertIn("TODO", drafts[0]["retire_when"])

    def test_a_green_run_drafts_nothing(self) -> None:
        campaign = {"runs": [{"run_id": "r2", "iterations": [
            {"iteration": 1, "green": True, "failing_check_ids": []}]}]}
        self.assertEqual(notes_bank.draft_from_campaign(campaign), [])


class SeedBankAndBrief(unittest.TestCase):
    def test_the_shipped_bank_is_valid_and_something_routes_to_the_author(self) -> None:
        """Invariants, not a content snapshot: the bank LEARNS (its first
        measured test retired both seed notes, exactly as designed), so a test
        pinning specific ids would fail every time the bank does its job."""
        bank = notes_bank.load_bank()  # load_bank validates every note
        self.assertGreaterEqual(len(bank["notes"]), 2)
        routed = notes_bank.relevant_notes(bank, "check-author", {"rendering", "pdf"})
        self.assertGreaterEqual(len(routed), 1,
                                "no active note routes to the author at all: the bank is dead")
        self.assertTrue(all(row["verification"]["status"] != "retired" for row in routed))
        # Retired notes stay in the bank as history but must never route.
        retired = [row for row in bank["notes"] if row["verification"]["status"] == "retired"]
        for note in retired:
            self.assertIn("records", note["verification"])
            self.assertTrue(note["verification"]["records"],
                            "a retired note must carry the measurement that killed it")

    def test_notes_land_in_the_brief_before_the_delivery_contract(self) -> None:
        """The author must read the lessons before deciding what to write."""
        detected = {"test": {"command": ["node", "--test", "t.test.js"], "runner": "node--test"}}
        bank = notes_bank.load_bank()
        routed = notes_bank.relevant_notes(bank, "check-author", {"rendering"})
        brief = author_role.build_brief(Path("."), "TASK", detected, notes=routed)
        self.assertIn("LESSONS FROM PRIOR FAILURES", brief)
        self.assertLess(brief.index("LESSONS FROM PRIOR FAILURES"), brief.index("HOW TO DELIVER YOUR WORK"))
        # and never any task's answer: the seed notes must stay class-level
        self.assertNotIn("citation-run-separated", brief)

    def test_without_notes_the_brief_is_unchanged(self) -> None:
        detected = {"test": {"command": ["node", "--test", "t.test.js"], "runner": "node--test"}}
        brief = author_role.build_brief(Path("."), "TASK", detected, notes=[])
        self.assertNotIn("LESSONS FROM PRIOR FAILURES", brief)


if __name__ == "__main__":
    unittest.main(verbosity=2)
