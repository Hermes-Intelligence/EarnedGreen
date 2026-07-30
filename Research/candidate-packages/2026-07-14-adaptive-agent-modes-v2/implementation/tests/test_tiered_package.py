#!/usr/bin/env python3
"""Every-environment-case tests for the tiered-loop package
(oracle_bootstrap + tiered_loop + support_council). Offline; strong-model
steps are injected responders; captures are tiny local scripts — python-only
and js-free so they run on any host."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import oracle_bootstrap
import support_council
import tiered_loop

CAPTURE = (
    "import json, pathlib\n"
    "text = pathlib.Path('module.txt').read_text(encoding='utf-8').strip()\n"
    "events = [f'word-{w}' for w in text.split()] or ['empty']\n"
    "print(json.dumps({'doc': events, 'stable': ['always-1', 'always-2']}))\n"
)
NONDET_CAPTURE = (
    "import json, random\n"
    "print(json.dumps({'doc': [f'r-{random.random()}'], 'stable': ['always-1']}))\n"
)


def make_tree(base: Path, name: str, module_text: str, capture_src: str = CAPTURE) -> Path:
    tree = base / name
    tree.mkdir(parents=True, exist_ok=True)
    (tree / "module.txt").write_text(module_text, encoding="utf-8")
    (tree / "capture.py").write_text(capture_src, encoding="utf-8")
    return tree


def cmd() -> list[str]:
    return ["{python}", "capture.py"]


class OracleBootstrap(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="tiered-pkg-")
        self.base = Path(self.tmp.name)
        self.suite = oracle_bootstrap.BootstrapSuite(self.base / "suite.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_relations_at_birth_pins_envelope_and_flags_nondeterminism(self):
        tree = make_tree(self.base, "birth", "alpha beta")
        outcome = self.suite.relations_at_birth(tree, cmd())
        self.assertEqual(outcome["pins_added"], 2)
        self.assertEqual(outcome["findings"], [])
        bad = make_tree(self.base, "nondet", "alpha", NONDET_CAPTURE)
        suite2 = oracle_bootstrap.BootstrapSuite(self.base / "suite2.json")
        outcome2 = suite2.relations_at_birth(bad, cmd())
        kinds = {f["kind"] for f in outcome2["findings"]}
        self.assertIn("determinism", kinds, "a nondeterministic stream is a finding, never a pin")

    def test_admission_rejects_vacuous_prose_and_duplicates(self):
        tree = make_tree(self.base, "base", "alpha beta")
        self.suite.relations_at_birth(tree, cmd())
        proposals = [
            {"id": "doc::gamma", "input_id": "doc", "relation": "count-direction",
             "kind": "word-gamma", "baseline": 0, "direction": "became-nonzero"},
            {"id": "doc::vacuous", "input_id": "doc", "relation": "count-direction",
             "kind": "word-alpha", "baseline": 0, "direction": "became-nonzero"},
            "just write it carefully",
            {"id": "doc::gamma", "input_id": "doc", "relation": "count-equal",
             "kind": "word-gamma", "expected": 1},
        ]
        results = self.suite.admit_proposals(proposals, tree, "spec")
        self.assertTrue(results[0]["admitted"], "a red-on-baseline predicate admits")
        self.assertFalse(results[1]["admitted"])
        self.assertIn("vacuous", results[1]["reason"].lower())
        self.assertFalse(results[2]["admitted"], "prose is rejected, never admitted")
        self.assertFalse(results[3]["admitted"])
        self.assertIn("duplicate", results[3]["reason"])

    def test_acceptance_freezes_envelope_and_surfaces_unmet_spec(self):
        tree = make_tree(self.base, "v0", "alpha")
        self.suite.relations_at_birth(tree, cmd())
        self.suite.admit_proposals(
            [{"id": "doc::gamma", "input_id": "doc", "relation": "count-direction",
              "kind": "word-gamma", "baseline": 0, "direction": "became-nonzero"}],
            tree, "spec")
        v1 = make_tree(self.base, "v1", "alpha beta")  # beta added, gamma still missing
        outcome = self.suite.freeze_acceptance(v1, accepted_by="owner")
        self.assertEqual(outcome["verdict"], "unmet-predicates-surfaced")
        self.assertEqual(outcome["unmet_predicates"], ["doc::gamma"])
        # the accepted envelope is the new floor: v0 must now be RED
        verdict_v0 = self.suite.evaluate_tree(tree)
        self.assertFalse(verdict_v0["green"], "regressing below an accepted iteration must be red")
        v2 = make_tree(self.base, "v2", "alpha beta gamma")
        outcome2 = self.suite.freeze_acceptance(v2, accepted_by="owner")
        self.assertEqual(outcome2["verdict"], "clean")
        self.assertTrue(self.suite.evaluate_tree(v2)["green"])

    def test_no_capture_command_fails_loudly_never_silently(self):
        with self.assertRaises(RuntimeError):
            self.suite.admit_proposals([], self.base, "spec")
        with self.assertRaises(RuntimeError):
            self.suite.freeze_acceptance(self.base, accepted_by="x")

    def test_work_surface_inputs_are_not_frozen_as_envelope(self):
        """From-scratch work: a capture dimension that is EMPTY today because the
        feature does not exist must not be pinned as 'stay empty'. Found live on
        the first real from-scratch task."""
        tree = make_tree(self.base, "ws", "alpha", (
            "import json, pathlib\n"
            "text = pathlib.Path('module.txt').read_text(encoding='utf-8').strip()\n"
            "print(json.dumps({'doc': [f'word-{w}' for w in text.split()], 'newfeature': []}))\n"))
        outcome = self.suite.relations_at_birth(tree, cmd(), exclude_inputs=["newfeature"])
        self.assertEqual(outcome["pins_added"], 1, "only the envelope input is pinned")
        self.assertNotIn("newfeature", [p["input_id"] for p in self.suite.data["predicates"]])
        self.suite.admit_proposals(
            [{"id": "newfeature::exists", "input_id": "newfeature",
              "relation": "count-direction", "kind": "thing", "baseline": 0,
              "direction": "became-nonzero"}], tree, "spec")
        built = make_tree(self.base, "ws-built", "alpha", (
            "import json, pathlib\n"
            "text = pathlib.Path('module.txt').read_text(encoding='utf-8').strip()\n"
            "print(json.dumps({'doc': [f'word-{w}' for w in text.split()], "
            "'newfeature': ['thing:a']}))\n"))
        self.assertTrue(self.suite.evaluate_tree(built)["green"],
                        "building the feature must not redden the envelope")
        frozen = self.suite.freeze_acceptance(built, accepted_by="owner")
        self.assertEqual(frozen["verdict"], "clean")
        self.assertNotIn("newfeature", [p["input_id"] for p in self.suite.data["predicates"]
                                        if p["provenance"]["source"] == "acceptance"])

    def test_status_reports_provenance_counts(self):
        tree = make_tree(self.base, "s", "alpha")
        self.suite.relations_at_birth(tree, cmd())
        status = self.suite.status()
        self.assertEqual(status["by_provenance"], {"relation": 2})


class Tiered(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="tiered-state-")
        self.state = tiered_loop.TieredState(Path(self.tmp.name) / "tiered.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_t1_fires_on_complexity_and_stays_quiet_on_simple(self):
        # council is opt-in until measured; with it enabled the complexity
        # signals behave as designed
        state = tiered_loop.TieredState(Path(self.tmp.name) / "t1.json",
                                        policy={"council_enabled": True})
        self.assertIsNone(state.assess_task_start({"files_planned": 2}))
        record = state.assess_task_start({"files_planned": 9, "symptom_families": 6})
        self.assertEqual(record["kind"], "council")
        self.assertIn("files", record["payload"]["hits"])

    def test_t3_stall_fires_once_per_fingerprint(self):
        iterations = [{"failure_fingerprint": "AAA"}, {"failure_fingerprint": "AAA"}]
        first = self.state.observe_iterations(iterations)
        self.assertEqual(first["trigger"], "T3-stall")
        self.assertIsNone(self.state.observe_iterations(iterations), "no duplicate escalation")

    def test_t5_family_repeat_escalates_to_single_review(self):
        iterations = [{"failure_fingerprint": "A", "failing_families": ["coverage"]},
                      {"failure_fingerprint": "B", "failing_families": ["coverage"]}]
        record = self.state.observe_iterations(iterations)
        self.assertEqual(record["trigger"], "T5-family-repeat")
        self.assertEqual(record["kind"], "review")

    def test_t2_pre_done_blocks_until_review_recorded_and_mechanical_passes_free(self):
        self.assertTrue(self.state.pre_done([])["ready"], "no unverified dims -> no toll")
        blocked = self.state.pre_done(["sources-filtering"])
        self.assertFalse(blocked["ready"])
        index = blocked["escalation_index"]
        with self.assertRaises(ValueError):
            self.state.record_response(index, {"notes": "looks fine"})  # no verdict = forms
        self.state.record_response(index, {
            "verdict": "approve", "reasons": ["read it"],
            # an approve must leave machinery or an honest declaration behind
            "not_mechanically_checkable": True, "not_checkable_reasons": ["judgement call"]})
        self.assertTrue(self.state.pre_done(["sources-filtering"])["ready"])
        self.assertFalse(self.state.pre_done(["sources-filtering", "new-dim"])["ready"],
                         "a NEW unverified dimension re-arms the gate")

    def test_t4_risk_gate_before_human_gate(self):
        self.assertIsNone(self.state.risk_gate(False, False))
        record = self.state.risk_gate(True, False)
        self.assertEqual(record["trigger"], "T4-risk")
        again = self.state.risk_gate(True, False)
        self.assertEqual(again["index"], record["index"], "same open escalation, not a new one")

    def test_support_budget_and_brief_filter(self):
        weak = self.state.support({"decision": "how to shard"})
        self.assertFalse(weak["granted"])
        brief = {"decision": "sharding", "options_considered": "a/b", "risks": "loss",
                 "what_i_might_be_missing": "rebalancing"}
        self.assertTrue(self.state.support(brief)["granted"])
        self.assertTrue(self.state.support(brief)["granted"])
        third = self.state.support(brief)
        self.assertFalse(third["granted"])
        self.assertIn("budget", third["reason"])

    def test_disabled_policy_is_fully_inert(self):
        state = tiered_loop.TieredState(Path(self.tmp.name) / "off.json",
                                        policy={"enabled": False})
        self.assertIsNone(state.assess_task_start({"files_planned": 99}))
        self.assertTrue(state.pre_done(["x"])["ready"])
        self.assertIsNone(state.risk_gate(True, True))


class Council(unittest.TestCase):
    @staticmethod
    def _responders(invariants, b_verdict="countersign"):
        def member_a(brief):
            if "RECONCILED DECISION MEMO" in brief:
                return json.dumps({"approach": "plan", "risks": ["r"], "do_nots": ["d"],
                                   "invariants": invariants, "notes_for_executor": []})
            if "CROSS-EXAMINATION" in brief:
                return json.dumps({"attacks": [{"target": "x", "failure": "y", "severity": "low"}]})
            return json.dumps({"approach": "A-plan", "edge_cases": [], "failure_modes": [],
                               "what_must_not_be_lost": ["data"]})

        def member_b(brief):
            if "COUNTERSIGN" in brief.upper():
                return json.dumps({"verdict": b_verdict, "reasons": ["ok"]})
            if "CROSS-EXAMINATION" in brief:
                return json.dumps({"attacks": []})
            return json.dumps({"approach": "B-plan", "edge_cases": ["e"], "failure_modes": [],
                               "what_must_not_be_lost": []})
        return {"member_a": member_a, "member_b": member_b}

    def test_agreed_memo_with_structured_invariants(self):
        invariants = [{"id": "doc::x", "input_id": "doc", "relation": "count-equal",
                       "kind": "word-x", "expected": 1}]
        outcome = support_council.run_council({"task": "t"}, self._responders(invariants))
        self.assertEqual(outcome["status"], "agreed")
        self.assertEqual(len(outcome["memo"]["invariants"]), 1)

    def test_prose_invariants_invalidate_the_memo(self):
        outcome = support_council.run_council({"task": "t"},
                                              self._responders(["be very careful"]))
        self.assertEqual(outcome["status"], "invalid-memo")
        self.assertIn("prose", outcome["validation"]["reason"])

    def test_dissent_routes_to_human_gate(self):
        invariants = [{"id": "doc::x", "input_id": "doc", "relation": "count-equal",
                       "kind": "word-x", "expected": 1}]
        outcome = support_council.run_council({"task": "t"},
                                              self._responders(invariants, b_verdict="dissent"))
        self.assertEqual(outcome["status"], "dissent")
        self.assertIn("HUMAN GATE", outcome["action"])


class JudgeAuthorityLimits(unittest.TestCase):
    """The research-driven hardening: a model's review never certifies."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="judge-limits-")
        self.state = tiered_loop.TieredState(Path(self.tmp.name) / "tiered.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_bare_approve_is_refused_predicates_or_declaration_required(self):
        index = self.state.pre_done(["wide-dim"])["escalation_index"]
        with self.assertRaises(ValueError) as raised:
            self.state.record_response(index, {"verdict": "approve", "reasons": ["read it"]})
        self.assertIn("proposed_predicates", str(raised.exception))
        # a declaration is an acceptable answer: it routes to human acceptance
        self.state.record_response(index, {"verdict": "approve",
                                           "not_mechanically_checkable": True,
                                           "not_checkable_reasons": ["taste"]})
        outcome = self.state.pre_done(["wide-dim"])
        self.assertTrue(outcome["ready"])
        self.assertEqual(outcome["manifest_provenance"], "reviewed-unverified")
        self.assertTrue(outcome["human_acceptance_required"])

    def test_a_block_does_not_unblock_done(self):
        """AUDIT F2: answeredness was being read as agreement."""
        index = self.state.pre_done(["d"])["escalation_index"]
        self.state.record_response(index, {"verdict": "block", "reasons": ["broken"]})
        self.assertFalse(self.state.pre_done(["d"])["ready"],
                         "a reviewer's objection must cost something")
        revise = self.state.pre_done(["d"])["escalation_index"]
        self.state.record_response(revise, {"verdict": "revise", "reasons": ["half done"]})
        self.assertFalse(self.state.pre_done(["d"])["ready"])

    def test_junk_predicates_and_stringy_declarations_are_refused(self):
        """AUDIT F6: ['ship it lol'] used to unblock done."""
        index = self.state.pre_done(["d"])["escalation_index"]
        with self.assertRaises(ValueError):
            self.state.record_response(index, {"verdict": "approve",
                                               "proposed_predicates": ["ship it lol"]})
        with self.assertRaises(ValueError):
            self.state.record_response(index, {"verdict": "approve",
                                               "not_mechanically_checkable": "false"})
        self.state.record_response(index, {
            "verdict": "approve",
            "proposed_predicates": [{"id": "doc::x", "input_id": "doc",
                                     "relation": "count-equal", "kind": "word-x", "expected": 1}]})
        self.assertTrue(self.state.pre_done(["d"])["ready"])

    def test_support_cannot_smuggle_the_council_past_the_policy(self):
        """AUDIT F8: support() ignored both switches."""
        brief = {"decision": "d", "options_considered": "o", "risks": "r",
                 "what_i_might_be_missing": "m"}
        self.assertEqual(self.state.support(brief)["kind"], "review",
                         "with the council off a self-request is served by a single review")
        off = tiered_loop.TieredState(Path(self.tmp.name) / "off2.json",
                                      policy={"enabled": False})
        self.assertFalse(off.support(brief)["granted"])

    def test_council_triggers_are_off_by_default_and_stall_degrades_to_review(self):
        self.assertIsNone(self.state.assess_task_start({"files_planned": 99,
                                                        "symptom_families": 99}),
                          "council must not fire before it is measured")
        stall = self.state.observe_iterations([{"failure_fingerprint": "X"},
                                               {"failure_fingerprint": "X"}])
        self.assertEqual(stall["kind"], "review", "stall still escalates, at the cheaper tier")
        on = tiered_loop.TieredState(Path(self.tmp.name) / "on.json",
                                     policy={"council_enabled": True})
        self.assertEqual(on.assess_task_start({"files_planned": 99})["kind"], "council")

    def test_manifest_rejects_bookkeeping_bugs(self):
        """AUDIT F9: duplicate dimension ids collapsed silently; id-less checks crashed."""
        import coverage_manifest
        with self.assertRaises(ValueError):
            coverage_manifest.build([{"id": "a"}, {"id": "a"}], [])
        with self.assertRaises(ValueError):
            coverage_manifest.build([{"id": "a"}], [{"covers": ["a"], "provenance": "spec"}])

    def test_manifest_never_promotes_a_reviewed_dimension_to_earned_green(self):
        import coverage_manifest
        manifest = coverage_manifest.build(
            [{"id": "wide", "statement": "taste"}, {"id": "narrow"}],
            [{"id": "review-1", "covers": ["wide"], "provenance": "reviewed-unverified"},
             {"id": "pred-1", "covers": ["narrow"], "provenance": "spec"}])
        self.assertEqual([row["id"] for row in manifest["verified"]], ["narrow"])
        wide = next(row for row in manifest["unverified"] if row["id"] == "wide")
        self.assertEqual(wide["reviewed_by"], ["review-1"])
        self.assertIn("not verification", wide["note"])
        self.assertIn("reviewed (NOT verified)", coverage_manifest.render(manifest))


class ProvisionalAndCalibration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="provisional-")
        self.base = Path(self.tmp.name)
        self.suite = oracle_bootstrap.BootstrapSuite(self.base / "suite.json", suspect_after=2)
        self.tree = make_tree(self.base, "v0", "alpha")
        self.suite.relations_at_birth(self.tree, cmd())

    def tearDown(self):
        self.tmp.cleanup()

    def _propose(self, kind: str):
        return [{"id": f"doc::{kind}", "input_id": "doc", "relation": "count-direction",
                 "kind": f"word-{kind}", "baseline": 0, "direction": "became-nonzero"}]

    def test_council_predicates_start_provisional_and_confirm_on_acceptance(self):
        self.suite.admit_proposals(self._propose("beta"), self.tree, "council")
        entry = next(p for p in self.suite.data["predicates"] if p["id"] == "doc::beta")
        self.assertEqual(entry["status"], "provisional",
                         "red-on-baseline proves a demand, never that the demand is right")
        good = make_tree(self.base, "good", "alpha beta")
        outcome = self.suite.freeze_acceptance(good, accepted_by="owner")
        self.assertIn("doc::beta", outcome["confirmed_predicates"])
        self.assertEqual(entry["status"], "confirmed")

    def test_a_confirmed_predicate_never_degrades_to_suspect(self):
        """AUDIT F3(b): deleting a working feature used to launder red into green."""
        self.suite.admit_proposals(self._propose("beta"), self.tree, "council")
        good = make_tree(self.base, "good2", "alpha beta")
        self.suite.freeze_acceptance(good, accepted_by="owner")
        regressed_a = make_tree(self.base, "reg-a", "alpha")
        regressed_b = make_tree(self.base, "reg-b", "alpha gamma")
        self.suite.freeze_acceptance(regressed_a, accepted_by="owner")
        outcome = self.suite.freeze_acceptance(regressed_b, accepted_by="owner")
        entry = next(p for p in self.suite.data["predicates"] if p["id"] == "doc::beta")
        self.assertEqual(entry["status"], "confirmed", "a regression is not a bad predicate")
        self.assertIn("doc::beta", outcome["unmet_predicates"])
        self.assertFalse(self.suite.evaluate_tree(regressed_b)["green"])

    def test_repeat_acceptance_of_the_same_tree_earns_no_suspicion(self):
        """AUDIT F3(a): two accepts of an UNCHANGED tree used to launder a predicate."""
        self.suite.admit_proposals(self._propose("zeta"), self.tree, "council")
        same = make_tree(self.base, "same", "alpha")
        for _ in range(4):
            outcome = self.suite.freeze_acceptance(same, accepted_by="me")
        self.assertEqual(outcome["suspect_predicates"], [])
        entry = next(p for p in self.suite.data["predicates"] if p["id"] == "doc::zeta")
        self.assertEqual(entry["status"], "provisional")
        self.assertTrue(outcome["repeat_acceptance"])
        self.assertFalse(self.suite.evaluate_tree(same)["green"])

    def test_envelope_regression_blocks_green_by_default(self):
        """AUDIT F5: destroying preserved behaviour used to ship green."""
        accepted = make_tree(self.base, "acc-env", "alpha beta gamma")
        self.suite.freeze_acceptance(accepted, accepted_by="owner")
        wrecked = make_tree(self.base, "wrecked", "gamma")
        verdict = self.suite.evaluate_tree(wrecked)
        self.assertFalse(verdict["green"], "the accepted floor must gate shipping")
        self.assertTrue(verdict["changed_pending_acceptance"])
        wip = self.suite.evaluate_tree(wrecked, work_in_progress=True)
        self.assertTrue(wip["green"], "mid-task the envelope is allowed to be in motion")

    def test_a_capture_error_is_never_green(self):
        broken = make_tree(self.base, "broken", "alpha", (
            "import json\nprint(json.dumps({'doc': {'__error__': 'boom'}, "
            "'stable': ['always-1', 'always-2']}))\n"))
        verdict = self.suite.evaluate_tree(broken, work_in_progress=True)
        self.assertFalse(verdict["green"])
        self.assertTrue(verdict["errors"])

    def test_acceptance_reports_crashed_inputs_instead_of_dropping_them(self):
        """AUDIT F7: acceptance was quieter than birth about the same condition."""
        crashing = make_tree(self.base, "crash", "alpha", (
            "import json\nprint(json.dumps({'doc': {'__error__': 'boom'}, "
            "'stable': ['always-1', 'always-2']}))\n"))
        outcome = self.suite.freeze_acceptance(crashing, accepted_by="owner")
        self.assertEqual(outcome["verdict"], "crashed-inputs")
        self.assertIn("doc", outcome["crashed_inputs"])

    def test_calibrate_ignores_envelope_pins(self):
        """AUDIT (claim 6): every envelope pin was labelled decoration by construction."""
        self.suite.admit_proposals(self._propose("beta"), self.tree, "spec")
        good = make_tree(self.base, "cal-good", "alpha beta")
        report = self.suite.calibrate(self.tree, good)
        self.assertEqual(report["decoration"], [])
        self.assertEqual(report["sound"], ["doc::beta"])
        self.assertTrue(report["not_calibratable_envelope"])

    def test_evaluate_and_calibrate_fail_loudly_without_a_capture_command(self):
        empty = oracle_bootstrap.BootstrapSuite(self.base / "empty.json")
        with self.assertRaises(RuntimeError):
            empty.evaluate_tree(self.tree)
        with self.assertRaises(RuntimeError):
            empty.calibrate(self.tree, self.tree)

    def test_repeatedly_unmet_predicate_becomes_suspect_and_stops_blocking(self):
        self.suite.admit_proposals(self._propose("zeta"), self.tree, "council")
        # DISTINCT accepted states: repeated acceptance of one unchanged tree is
        # not evidence (see the repeat-acceptance test)
        for name, text in (("a1", "alpha beta"), ("a2", "alpha beta delta")):
            accepted = make_tree(self.base, name, text)
            outcome = self.suite.freeze_acceptance(accepted, accepted_by="owner")
        self.assertIn("doc::zeta", outcome["suspect_predicates"])
        verdict = self.suite.evaluate_tree(accepted)
        self.assertTrue(verdict["green"], "a suspect predicate no longer blocks")
        self.assertIn("doc::zeta", verdict["suspect_red"], "but it is still reported")

    def test_calibrate_names_decoration_and_fakeable_predicates(self):
        self.suite.admit_proposals(self._propose("beta"), self.tree, "spec")
        good = make_tree(self.base, "acc", "alpha beta")
        self.suite.freeze_acceptance(good, accepted_by="owner")
        # a hollow tree that emits the expected event without doing the work
        hollow = make_tree(self.base, "hollow", "ignored", (
            "import json\nprint(json.dumps({'doc': ['word-alpha', 'word-beta'], "
            "'stable': ['always-1', 'always-2']}))\n"))
        report = self.suite.calibrate(self.tree, good, hollow)
        row = next(r for r in report["rows"] if r["id"] == "doc::beta")
        self.assertTrue(row["null"], "it fails on the baseline")
        self.assertTrue(row["golden"], "it holds on the accepted implementation")
        self.assertEqual(row["verdict"], "fakeable",
                         "a hardcoded stream satisfies it — the corpus is too predictable here")
        self.assertIn("doc::beta", report["fakeable"])


class CaptureAdversary(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="capture-adv-")
        self.base = Path(self.tmp.name)
        self.suite = oracle_bootstrap.BootstrapSuite(self.base / "suite.json")
        self.tree = make_tree(self.base, "work", "alpha")
        self.suite.relations_at_birth(self.tree, cmd())
        self.suite.admit_proposals(
            [{"id": "doc::gamma", "input_id": "doc", "relation": "count-direction",
              "kind": "word-gamma", "baseline": 0, "direction": "became-nonzero"}],
            self.tree, "spec")

    def tearDown(self):
        self.tmp.cleanup()

    def test_hollow_attack_that_satisfies_the_suite_marks_the_corpus_fakeable(self):
        import capture_adversary
        attack = {"capture.py": ("import json\nprint(json.dumps({'doc': "
                                 "['word-alpha', 'word-gamma'], 'stable': "
                                 "['always-1', 'always-2']}))\n")}
        outcome = capture_adversary.evaluate(self.suite, self.tree, attack,
                                             self.base / "scratch")
        self.assertEqual(outcome["verdict"], "corpus-fakeable")
        self.assertIn("widen the corpus", outcome["action"])

    def test_honest_looking_attack_that_fails_leaves_the_corpus_holding(self):
        import capture_adversary
        attack = {"module.txt": "alpha"}  # changes nothing relevant
        outcome = capture_adversary.evaluate(self.suite, self.tree, attack,
                                             self.base / "scratch2")
        self.assertEqual(outcome["verdict"], "corpus-holds")
        self.assertIn("evidence, not proof", outcome["caveat"])

    def test_crashing_attack_is_never_reported_as_defeated(self):
        import capture_adversary
        attack = {"capture.py": "raise SystemExit(3)\n"}
        outcome = capture_adversary.evaluate(self.suite, self.tree, attack,
                                             self.base / "scratch3")
        self.assertEqual(outcome["verdict"], "attack-failed")

    def test_path_escape_is_refused_including_sibling_prefix(self):
        """AUDIT F4: a bare startswith let '<scratch>-evil/x' through."""
        import capture_adversary
        for escape in ("../escape.txt", "../scratch5-evil/pwned.txt",
                       "..\\sibling\\pwned.txt", "sub/../../out.txt"):
            outcome = capture_adversary.evaluate(self.suite, self.tree,
                                                 {escape: "x"}, self.base / "scratch5")
            self.assertEqual(outcome["verdict"], "attack-failed", f"escaped via {escape}")
            self.assertIn("outside the workspace", outcome["reason"])
        self.assertFalse((self.base / "scratch5-evil").exists(),
                         "nothing may be written outside the sandbox")

    def test_brief_carries_predicates_and_asks_for_hollow_work(self):
        import capture_adversary
        brief = capture_adversary.build_brief(self.suite.data["predicates"], cmd(),
                                              {"capture.py": "..."})
        self.assertIn("AS LITTLE OF THE REAL WORK AS POSSIBLE", brief)
        self.assertIn("doc::gamma", brief)


class ReviewerProbe(unittest.TestCase):
    def test_flattered_reviewer_is_detected(self):
        import reviewer_probe
        outcome = reviewer_probe.run_probe(
            "taste", "context",
            lambda _b: json.dumps({"verdict": "approve", "reasons": ["looks thorough"]}))
        self.assertEqual(outcome["verdict"], "reviewer-flattered")
        self.assertIn("process-only", outcome["consequence"])

    def test_sound_reviewer_blocks_hollow_work(self):
        import reviewer_probe
        outcome = reviewer_probe.run_probe(
            "taste", "context",
            lambda _b: json.dumps({"verdict": "block", "reasons": ["the change is a placeholder"]}))
        self.assertEqual(outcome["verdict"], "reviewer-sound")

    def test_unusable_reply_measures_nothing(self):
        import reviewer_probe
        self.assertEqual(reviewer_probe.run_probe("d", "c", lambda _b: "sure, looks fine")["verdict"],
                         "probe-invalid")

    def test_probe_submission_is_hollow_by_construction(self):
        import reviewer_probe
        submission = reviewer_probe.build_probe_submission("dim", "ctx")
        self.assertTrue(any(marker in submission["actual_change"]
                            for marker in reviewer_probe.HOLLOW_MARKERS))


class EndToEnd(unittest.TestCase):
    def test_council_invariants_flow_into_the_suite_and_hold_the_executor(self):
        with tempfile.TemporaryDirectory(prefix="tiered-e2e-") as tmp:
            base = Path(tmp)
            tree = make_tree(base, "work", "alpha")
            suite = oracle_bootstrap.BootstrapSuite(base / "suite.json")
            suite.relations_at_birth(tree, cmd())
            invariants = [{"id": "doc::delta", "input_id": "doc", "relation": "count-direction",
                           "kind": "word-delta", "baseline": 0, "direction": "became-nonzero"}]
            outcome = support_council.run_council({"task": "add delta"},
                                                  Council._responders(invariants))
            self.assertEqual(outcome["status"], "agreed")
            admitted = suite.admit_proposals(outcome["memo"]["invariants"], tree, "council")
            self.assertTrue(admitted[0]["admitted"])
            # the executor cannot claim green without honouring the council
            self.assertFalse(suite.evaluate_tree(tree, work_in_progress=True)["green"])
            done = make_tree(base, "done", "alpha delta")
            # mid-task the envelope is in motion, so the loop reads proposals...
            self.assertTrue(suite.evaluate_tree(done, work_in_progress=True)["green"])
            # ...and shipping requires an acceptance that blesses the new envelope
            self.assertFalse(suite.evaluate_tree(done)["green"])
            frozen = suite.freeze_acceptance(done, accepted_by="owner")
            self.assertEqual(frozen["verdict"], "clean")
            self.assertTrue(suite.evaluate_tree(done)["green"])
            self.assertEqual(suite.status()["by_provenance"],
                             {"relation": 2, "council": 1, "acceptance": 2})


if __name__ == "__main__":
    unittest.main(verbosity=2)
