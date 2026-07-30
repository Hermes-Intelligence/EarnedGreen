#!/usr/bin/env python3
"""ORACLE BOOTSTRAP — the self-hardening oracle for work with NO answer key.

The measured trail this implements:
  * a mechanical oracle needs an answer key; genuinely new work has none
    (three-regime map, Stable 0.6.x) — but the environment can BUILD one as
    the work happens, from four sources, each mechanically validated:
      relation   what the new code must not be (non-deterministic, crashing)
                 — minable from birth, no history needed
      spec       countable observables proposed FROM THE OWNER'S SPEC by a
                 strong model, admitted only if RED on the pre-work baseline
                 (a spec predicate the old code already satisfies demands
                 nothing — the vacuity lesson, applied to data predicates)
      council    invariants from a support-council decision memo — same
                 admission path; PROSE IS REJECTED (the findings-as-forms
                 lesson: advice that is not a predicate evaporates)
      acceptance every ACCEPTED iteration is captured and its envelope
                 frozen — "new" becomes "old" immediately, so iteration N+1
                 builds against pinned iteration N
      finding    a confirmed reviewer finding with a countable observable
                 becomes a predicate the loop then enforces
  * self-AUTHORED checks bought zero lift (P1 falsified) — so nothing here
    trusts an author: every predicate passes the red-on-baseline gate, and
    spec predicates are re-verified GREEN at acceptance time (an unmet spec
    predicate is surfaced for a human decision, never silently dropped).

The suite lives in one JSON file, every predicate carrying provenance; the
coverage manifest renders these provenances so green is always typed.
Zero provider calls in this module: strong-model steps are BRIEFS the driving
session executes with its own subagents (the proven earned-green pattern).
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import diff_oracle

CAPTURE_TIMEOUT = 300
BOOTSTRAP_PROVENANCES = ("relation", "spec", "council", "acceptance", "finding")
RELATIONS_EVALUABLE = ("equal", "kinds-superset", "count-direction", "count-equal")


def capture(command: list[str], cwd: Path) -> dict[str, Any]:
    resolved = [sys.executable if part == "{python}" else part for part in command]
    completed = subprocess.run(resolved, cwd=cwd, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=CAPTURE_TIMEOUT)
    if completed.returncode != 0:
        raise RuntimeError(f"capture exited {completed.returncode}: {completed.stderr[-500:]}")
    streams = json.loads(completed.stdout)
    if not isinstance(streams, dict) or not streams:
        raise RuntimeError("capture printed no streams")
    return streams


class BootstrapSuite:
    """The growing, provenance-typed predicate suite for one piece of work."""

    def __init__(self, path: Path, suspect_after: int = 2):
        self.path = path
        self.suspect_after = suspect_after
        if path.exists():
            self.data = json.loads(path.read_text(encoding="utf-8-sig"))
        else:
            self.data = {"schema_version": 1, "capture_command": None,
                         "predicates": [], "log": []}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=1) + "\n",
                             encoding="utf-8")

    # -- internals ---------------------------------------------------------------

    def _ids(self) -> set[str]:
        return {p["id"] for p in self.data["predicates"]}

    def _add(self, predicate: dict, provenance: str, note: str) -> dict:
        # PROVISIONAL until an acceptance proves the predicate is satisfiable.
        # Red-on-baseline (our null slot) proves a proposal DEMANDS something;
        # it cannot prove the demand is RIGHT. The published triad that matches
        # our machinery (null / golden / adversarial) fills the golden slot from
        # a known-good implementation — for new work no such implementation
        # exists YET, so acceptance is our golden and confirmation waits for it.
        # This is also the guard against council error amplification: a wrong
        # invariant is admissible, so it must be falsifiable later.
        status = "provisional" if provenance in ("spec", "council", "finding") else "confirmed"
        entry = dict(predicate, provenance={"source": provenance, "note": note},
                     status=status, unmet_at_acceptances=0)
        self.data["predicates"].append(entry)
        self.data["log"].append({"event": "admitted", "id": predicate["id"],
                                 "source": provenance, "note": note, "status": status})
        return entry

    def _reject(self, predicate_id: str, reason: str) -> dict:
        self.data["log"].append({"event": "rejected", "id": predicate_id, "reason": reason})
        return {"id": predicate_id, "admitted": False, "reason": reason}

    @staticmethod
    def _structural_error(predicate: dict) -> str | None:
        if not isinstance(predicate, dict):
            return "not an object"
        if not predicate.get("id") or not predicate.get("input_id"):
            return "missing id/input_id"
        relation = predicate.get("relation", "equal" if "projection" in predicate else None)
        if relation is None:
            return "PROSE OR SHAPELESS: a predicate needs relation/projection fields — advice that is not mechanically evaluable is rejected by design"
        if relation not in RELATIONS_EVALUABLE:
            return f"unknown relation {relation!r}"
        if relation == "equal" and "projection" not in predicate:
            return "equal relation needs a projection"
        if relation in ("count-direction",) and not predicate.get("direction"):
            return "count-direction needs direction+baseline"
        return None

    # -- source 1: relations at birth ---------------------------------------------

    def relations_at_birth(self, tree: Path, capture_command: list[str],
                           exclude_inputs: list[str] | None = None) -> dict:
        """Totality + determinism findings NOW, envelope pins FORWARD — the
        no-history oracle a brand-new module gets on day one.

        `exclude_inputs` names the WORK SURFACE: inputs whose whole point is to
        change (a capture dimension that is empty today because the feature does
        not exist yet). Pinning those at birth would demand that the work never
        happen — found the first time this ran against a real from-scratch task,
        where the wiring dimension was legitimately empty on the baseline."""
        self.data["capture_command"] = capture_command
        self.data["work_surface_inputs"] = sorted(exclude_inputs or [])
        first = capture(capture_command, tree)
        second = capture(capture_command, tree)
        findings, added = [], 0
        for input_id in sorted(first):
            if input_id in (exclude_inputs or []):
                continue
            stream = first[input_id]
            if not isinstance(stream, list):
                findings.append({"kind": "totality", "input_id": input_id,
                                 "detail": f"{stream!r:.160}"})
                continue
            if second.get(input_id) != stream:
                findings.append({"kind": "determinism", "input_id": input_id})
                continue
            pin_id = f"{input_id}::birth-seq"
            if pin_id not in self._ids():
                self._add({"id": pin_id, "input_id": input_id,
                           "projection": "seq", "expected": stream},
                          "relation", "envelope at birth")
                added += 1
        self.data["log"].append({"event": "relations-at-birth", "pins": added,
                                 "findings": findings})
        return {"pins_added": added, "findings": findings}

    # -- sources 2/3/5: proposed predicates through the red-on-baseline gate -------

    def admit_proposals(self, proposals: list[dict], baseline_tree: Path,
                        provenance: str, note: str = "",
                        hollow_tree: Path | None = None) -> list[dict]:
        """The single admission path for spec / council / finding predicates.

        Gate: structurally evaluable AND RED on the admission surface AND not a
        duplicate. Red-on-baseline is the vacuity gate for data predicates —
        a proposal the current code already satisfies demands nothing new.

        `hollow_tree` switches the admission surface, and it exists because
        red-on-baseline QUIETLY GUTS the instrument in the from-scratch regime.
        When the baseline does not contain the surface at all, "the board does not
        overflow its viewport" is trivially true of a page with no board — so the
        gate does its job, rejects the predicate as vacuous, and the dimension
        ships uncovered. That is not hypothetical: it is exactly what happened on
        family-4, and the owner found that precise defect by eye an hour later.

        The fix is not to weaken the gate; it is to point it at the right surface.
        A HOLLOW fixture — the deliberate fake that satisfies the letter of the
        task and nothing else — is the from-scratch regime's baseline. A predicate
        red on the hollow build demands something a fake cannot supply, which is
        the property red-on-baseline was buying all along.
        """
        if provenance not in ("spec", "council", "finding"):
            raise ValueError(f"admit_proposals is for spec/council/finding, got {provenance!r}")
        if not self.data.get("capture_command"):
            raise RuntimeError("suite has no capture_command: run relations_at_birth first")
        admission_tree = hollow_tree if hollow_tree is not None else baseline_tree
        surface = "hollow" if hollow_tree is not None else "baseline"
        streams = capture(self.data["capture_command"], admission_tree)
        results = []
        for proposal in proposals:
            error = self._structural_error(proposal)
            if error:
                pid = proposal.get("id", "?") if isinstance(proposal, dict) else repr(proposal)[:60]
                results.append(self._reject(str(pid), error))
                continue
            if proposal["id"] in self._ids():
                results.append(self._reject(proposal["id"], "duplicate id"))
                continue
            outcome = diff_oracle.evaluate([proposal], streams)
            if outcome["errors"]:
                results.append(self._reject(
                    proposal["id"],
                    f"not evaluable on {surface}: {outcome['errors'][0].get('reason', '')[:120]}"))
                continue
            if outcome["green"]:
                results.append(self._reject(
                    proposal["id"],
                    f"GREEN ON {surface.upper()} (vacuous): "
                    + ("a deliberately hollow build already satisfies it — a fake would pass it"
                       if surface == "hollow" else
                       "the pre-work code already satisfies it — it demands nothing")))
                continue
            entry = self._add(proposal, provenance, f"{note} [admitted red-on-{surface}]".strip())
            results.append({"id": entry["id"], "admitted": True})
        return results

    # -- source 4: acceptance freezing ---------------------------------------------

    def freeze_acceptance(self, tree: Path, accepted_by: str) -> dict:
        """An ACCEPTED iteration becomes the new floor: its envelope is pinned,
        and every spec/council/finding predicate is re-verified GREEN on it.
        Unmet ones are SURFACED for a human decision — never silently dropped,
        never silently kept red."""
        if not self.data.get("capture_command"):
            raise RuntimeError("suite has no capture_command: run relations_at_birth first")
        streams = capture(self.data["capture_command"], tree)
        # An acceptance of the SAME state is not new evidence about a predicate.
        # Without this, two `awbp accept` calls on an unchanged tree launder any
        # unmet predicate into `suspect` and turn red green — the agent would be
        # its own accepter and its own judge.
        fingerprint = hashlib.sha256(
            json.dumps(streams, sort_keys=True, ensure_ascii=False,
                       default=str).encode("utf-8")).hexdigest().upper()
        repeat_acceptance = fingerprint == self.data.get("last_acceptance_fingerprint")
        self.data["last_acceptance_fingerprint"] = fingerprint

        crashed = [input_id for input_id, stream in sorted(streams.items())
                   if not isinstance(stream, list)]
        unmet, confirmed, suspect = [], [], []
        for predicate in self.data["predicates"]:
            if predicate["provenance"]["source"] not in ("spec", "council", "finding"):
                continue
            outcome = diff_oracle.evaluate([predicate], streams)
            if outcome["green"]:
                # GOLDEN slot filled: the accepted implementation satisfies it,
                # so the demand is real AND satisfiable — provisional no more.
                if predicate.get("status") != "confirmed":
                    predicate["status"] = "confirmed"
                    confirmed.append(predicate["id"])
                predicate["unmet_at_acceptances"] = 0
                continue
            unmet.append(predicate["id"])
            if predicate.get("status") == "confirmed":
                # It held on an accepted implementation once, so the predicate is
                # satisfiable and this is a REGRESSION, not a bad predicate. A
                # confirmed predicate never degrades to suspect — otherwise the
                # mechanism built to kill wrong demands would bury real defects.
                continue
            if repeat_acceptance:
                continue
            predicate["unmet_at_acceptances"] = predicate.get("unmet_at_acceptances", 0) + 1
            if predicate["unmet_at_acceptances"] >= self.suspect_after:
                # Repeatedly unmet across ACCEPTED work is evidence about the
                # PREDICATE, not the work: the same earned-persistence rule the
                # notes bank uses, applied to proposals. Suspect predicates stop
                # blocking green and are surfaced for a person to kill or keep.
                if predicate.get("status") != "suspect":
                    predicate["status"] = "suspect"
                    suspect.append(predicate["id"])
        frozen = 0
        work_surface = set(self.data.get("work_surface_inputs") or [])
        for input_id, stream in sorted(streams.items()):
            if input_id in work_surface:
                # the work surface is what the proposals speak for; freezing it
                # as an envelope would pin one arm's shape as the only shape
                continue
            if not isinstance(stream, list):
                continue  # reported as a crashed input below, never silently dropped
            # acceptance is the authority on the envelope: earlier birth/accepted
            # pins for this input are UPDATED to the accepted stream (an accepted
            # change is never a regression; an unaccepted one still reddens).
            # Matched by PROVENANCE, not by id suffix — a proposal that happens to
            # be named "<input>::birth-seq" must not have its expectation rewritten.
            for stale in self.data["predicates"]:
                if (stale["input_id"] == input_id
                        and stale["provenance"]["source"] == "relation"):
                    stale["expected"] = stream
                    stale["provenance"]["note"] = f"superseded by acceptance ({accepted_by})"
            pin_id = f"{input_id}::accepted-seq"
            existing = next((p for p in self.data["predicates"] if p["id"] == pin_id), None)
            if existing is not None:
                existing["expected"] = stream
                existing["provenance"] = {"source": "acceptance",
                                          "note": f"re-frozen; accepted_by={accepted_by}"}
            else:
                self._add({"id": pin_id, "input_id": input_id,
                           "projection": "seq", "expected": stream},
                          "acceptance", f"accepted_by={accepted_by}")
            frozen += 1
        self.data["log"].append({"event": "acceptance-frozen", "by": accepted_by,
                                 "inputs": frozen, "unmet_predicates": unmet,
                                 "confirmed": confirmed, "newly_suspect": suspect,
                                 "crashed_inputs": crashed,
                                 "repeat_acceptance": repeat_acceptance})
        verdict = "clean"
        if crashed:
            # freezing an envelope around a crashing input would pin the crash as
            # correct behaviour; relations_at_birth calls this a totality finding
            # and acceptance must not be quieter than birth
            verdict = "crashed-inputs"
        elif unmet:
            verdict = "unmet-predicates-surfaced"
        return {"frozen_inputs": frozen, "unmet_predicates": unmet,
                "confirmed_predicates": confirmed, "suspect_predicates": suspect,
                "crashed_inputs": crashed, "repeat_acceptance": repeat_acceptance,
                "verdict": verdict}

    # -- evaluation & status --------------------------------------------------------

    def evaluate_tree(self, tree: Path, work_in_progress: bool = False) -> dict:
        """Two verdicts, because new work needs both:
          * `proposals_green` — do the spec/council/finding predicates hold? This
            is what the LOOP iterates against while the work is unfinished.
          * `green` — proposals hold AND the accepted envelope is intact. This is
            what SHIPPING means. Envelope divergence is a regression until an
            acceptance blesses it, so it blocks by default: an implementation
            that satisfies its new predicates while destroying preserved
            behaviour is the exact silent defect this environment exists to
            catch, and reporting it in a side field was letting it ship.
        `work_in_progress=True` relaxes green to proposals only, for mid-task use
        where the envelope is legitimately in motion."""
        if not self.data.get("capture_command"):
            raise RuntimeError("suite has no capture_command: run relations_at_birth first")
        streams = capture(self.data["capture_command"], tree)
        proposals = [p for p in self.data["predicates"]
                     if p["provenance"]["source"] in ("spec", "council", "finding")
                     and p.get("status") != "suspect"]
        suspects = [p for p in self.data["predicates"] if p.get("status") == "suspect"]
        envelope = [p for p in self.data["predicates"]
                    if p["provenance"]["source"] in ("relation", "acceptance")]
        proposal_outcome = diff_oracle.evaluate(proposals, streams)
        envelope_outcome = diff_oracle.evaluate(envelope, streams)
        suspect_outcome = diff_oracle.evaluate(suspects, streams) if suspects else {
            "red_predicate_ids": [], "errors": []}
        envelope_broken = envelope_outcome["red_predicate_ids"]
        errors = proposal_outcome["errors"] + envelope_outcome["errors"]
        return {"green": bool(proposal_outcome["green"]
                              and not errors
                              and (work_in_progress or not envelope_broken)),
                "proposals_green": proposal_outcome["green"],
                "red_predicate_ids": proposal_outcome["red_predicate_ids"],
                # an input the capture could not produce is not a pass: an error
                # never counts as green, in either mode
                "errors": errors,
                "changed_pending_acceptance": envelope_broken,
                # suspect predicates are reported, never blocking: they failed
                # repeatedly against ACCEPTED work, so the evidence points at them
                "suspect_red": suspect_outcome["red_predicate_ids"]}

    def status(self) -> dict:
        by_source: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for predicate in self.data["predicates"]:
            source = predicate["provenance"]["source"]
            by_source[source] = by_source.get(source, 0) + 1
            state = predicate.get("status", "confirmed")
            by_status[state] = by_status.get(state, 0) + 1
        return {"predicates": len(self.data["predicates"]), "by_provenance": by_source,
                "by_status": by_status, "log_events": len(self.data["log"])}

    def calibrate(self, baseline_tree: Path, accepted_tree: Path,
                  hollow_tree: Path | None = None) -> dict:
        """THE FULL TRIAD, run retroactively once an accepted state exists.

        Our machinery matched an independently published admission triad
        (null / golden / adversarial) on two slots and left the third empty for
        new work: there was no known-good implementation at admission time.
        After an acceptance there is one, so every predicate can finally be
        graded on all three:
          null        RED on the pre-work baseline (it demands something)
          golden      GREEN on the accepted implementation (the demand is real)
          adversarial RED on a hollow implementation, when one is supplied
                      (it cannot be satisfied by faking)
        A predicate failing null or golden is DECORATION and is named as such.

        Only PROPOSALS are calibrated. Envelope pins (relation/acceptance) are
        green on the baseline by construction — that is their job, they preserve
        what already worked — so grading them against a null slot would label
        every one of them decoration and drown the real signal."""
        if not self.data.get("capture_command"):
            raise RuntimeError("suite has no capture_command: run relations_at_birth first")
        base = capture(self.data["capture_command"], baseline_tree)
        good = capture(self.data["capture_command"], accepted_tree)
        hollow = capture(self.data["capture_command"], hollow_tree) if hollow_tree else None
        rows = []
        calibratable = [p for p in self.data["predicates"]
                        if p["provenance"]["source"] in ("spec", "council", "finding")]
        for predicate in calibratable:
            null_ok = not diff_oracle.evaluate([predicate], base)["green"]
            golden_ok = diff_oracle.evaluate([predicate], good)["green"]
            adversarial_ok = None
            if hollow is not None:
                adversarial_ok = not diff_oracle.evaluate([predicate], hollow)["green"]
            verdict = "sound"
            if not null_ok:
                verdict = "decoration-vacuous"
            elif not golden_ok:
                verdict = "decoration-unsatisfiable"
            elif adversarial_ok is False:
                verdict = "fakeable"
            rows.append({"id": predicate["id"], "source": predicate["provenance"]["source"],
                         "null": null_ok, "golden": golden_ok,
                         "adversarial": adversarial_ok, "verdict": verdict})
        summary: dict[str, int] = {}
        for row in rows:
            summary[row["verdict"]] = summary.get(row["verdict"], 0) + 1
        envelope_ids = [p["id"] for p in self.data["predicates"]
                        if p["provenance"]["source"] in ("relation", "acceptance")]
        self.data["log"].append({"event": "calibrated", "summary": summary})
        return {"rows": rows, "summary": summary,
                "sound": [r["id"] for r in rows if r["verdict"] == "sound"],
                "decoration": [r["id"] for r in rows if r["verdict"].startswith("decoration")],
                "fakeable": [r["id"] for r in rows if r["verdict"] == "fakeable"],
                "not_calibratable_envelope": envelope_ids}


def spec_brief(spec_text: str, capture_command: list[str], sample_streams: dict) -> str:
    """The brief a STRONG model receives to propose spec-first predicates.
    The driving session runs this with its own subagent; the JSON reply goes to
    admit_proposals(..., provenance='spec')."""
    return (
        "You are proposing MECHANICAL acceptance predicates from a specification, BEFORE the work "
        "is done. You never see the future implementation; you pin observable consequences of the "
        "spec's rules on the given capture surface.\n\n"
        "SPECIFICATION:\n" + spec_text.strip() + "\n\n"
        "CAPTURE SURFACE: running " + json.dumps(capture_command) +
        " in the workspace prints {input_id: [event, ...]}. Sample of the CURRENT (pre-work) "
        "streams:\n" + json.dumps(sample_streams, ensure_ascii=False)[:4000] + "\n\n"
        "Reply with ONLY a JSON array of predicates. Allowed shapes:\n"
        '  {"id": "<input>::<name>", "input_id": "<input>", "relation": "kinds-superset", "expected": ["kind", ...]}\n'
        '  {"id": "...", "input_id": "...", "relation": "count-direction", "kind": "<event-kind>", "baseline": <n>, "direction": "became-nonzero|became-zero|increased|decreased"}\n'
        '  {"id": "...", "input_id": "...", "relation": "count-equal", "kind": "<event-kind>", "expected": <n>}\n'
        "Rules learned from measurement — follow them exactly:\n"
        "  * every predicate must FAIL on the current streams (it demands the new behaviour; "
        "vacuous proposals are mechanically rejected);\n"
        "  * pin outcomes the spec states, never rendering/formatting choices the spec leaves free "
        "(over-constraint proposals will die at acceptance time and be surfaced against you);\n"
        "  * prefer counts and kind-presence over exact sequences;\n"
        "  * NO prose, no explanations — prose is rejected by the validator."
    )
