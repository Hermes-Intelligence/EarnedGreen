#!/usr/bin/env python3
"""TIERED LOOP — model-tier escalation policy over the verification loop.

Design constraints, each from a measurement:
  * the weak model does not know what it does not know (the universal-neglect
    families) — so MECHANICAL triggers carry the load and self-requests are a
    budgeted bonus;
  * agent self-assessment is worthless as verification — escalations produce
    evidence artifacts the gate REQUIRES, never advice the agent may ignore;
  * this module never calls a provider: it emits BRIEFS and consumes recorded
    RESPONSES (the earned-green daily-use pattern), so any fork works without
    integration; benchmark runners inject responders the same way.

Forced triggers:
  T1 task-start complexity  -> council   (many files / protected paths /
                                          high unverified share / many
                                          symptom families)
  T2 pre-done unverified    -> review    (the coverage manifest's NAMED
                                          dimensions — and ONLY those — go to
                                          the strong model; gate refuses done
                                          without the recorded review)
  T3 loop stall             -> council   (same failure fingerprint twice — the
                                          measured no-progress state)
  T5 same family red twice  -> review
  T4 risk gate              -> review    (protected files / critical mode,
                                          BEFORE the human gate)
Self-request: `support(brief)` — structured brief required, hard budget.
Cost ladder: mechanical -> single review -> council (T1/T3 + self-request only).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_POLICY = {
    "enabled": True,
    # COUNCIL IS OFF BY DEFAULT — our own rule applied to our newest mechanism.
    # External evidence (Google, 180 configurations x 5 architectures): multi-agent
    # systems amplify errors 17.2x when independent and ~4.4x when centralized, and
    # the help/harm split by task shape is +80.9% / -39..-70%. Agent teams also cost
    # ~7x tokens. An unmeasured mechanism does not ship enabled: the review tier
    # (T2/T4/T5) is on, the council tier (T1/T3) waits for the campaign.
    "council_enabled": False,
    "executor_profile": "fast-low-risk",
    "reviewer_profile": "deep-implementation",
    "council_profiles": ["architecture-high-risk", "adversarial-review"],
    "support_budget": 2,
    "stall_repeats": 2,
    "family_red_repeats": 2,
    "complexity": {"max_files": 5, "max_symptom_families": 4, "max_unverified_share": 0.4},
}

REQUIRED_BRIEF_FIELDS = ("decision", "options_considered", "risks", "what_i_might_be_missing")

# A strong-model review is a JUDGE, and judges are now quantified as unreliable:
# reported pass rates of 0.72-0.94 at 0.20 true accuracy under self-play, with
# ensembling failing to rescue them (55% acceptance), and consistency measurably
# distinct from validity across 21 judges / ~541k judgments. So a review NEVER
# upgrades a dimension to EARNED GREEN here: it either hands back mechanically
# admissible predicates, or it declares the dimension not mechanically checkable
# and the manifest records it as reviewed-unverified for a human to accept.
REVIEW_PROVENANCE = "reviewed-unverified"


class TieredState:
    """Escalation ledger for one task; persisted beside the run."""

    def __init__(self, path: Path, policy: dict | None = None):
        self.path = path
        if path.exists():
            self.data = json.loads(path.read_text(encoding="utf-8-sig"))
        else:
            self.data = {"schema_version": 1, "policy": dict(DEFAULT_POLICY),
                         "escalations": [], "support_spent": 0}
        if policy:
            self.data["policy"].update(policy)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=1) + "\n",
                             encoding="utf-8")

    @property
    def policy(self) -> dict:
        return self.data["policy"]

    # -- escalation records ---------------------------------------------------------

    def _open(self, trigger: str, kind: str, payload: dict) -> dict:
        record = {"index": len(self.data["escalations"]), "trigger": trigger,
                  "kind": kind, "payload": payload, "status": "open", "response": None}
        self.data["escalations"].append(record)
        return record

    def record_response(self, index: int, response: dict) -> dict:
        record = self.data["escalations"][index]
        if not isinstance(response, dict) or not response.get("verdict"):
            raise ValueError("a recorded escalation response needs a structured verdict "
                             "(advice without a verdict is the forms failure mode)")
        if record["kind"] == "review" and response["verdict"] == "approve":
            # An approving judge must leave something behind that is not its own
            # opinion: either predicates the machinery can admit, or an explicit
            # statement that this dimension cannot be checked mechanically (which
            # routes it to human acceptance). Bare approval is refused — and so is
            # a bag of predicate-SHAPED junk: each proposal is structurally
            # validated here with the same validator admission uses, so a
            # flattered reviewer cannot unblock done with ["ship it"].
            import oracle_bootstrap
            proposals = response.get("proposed_predicates") or []
            if not isinstance(proposals, list):
                raise ValueError("proposed_predicates must be a list")
            malformed = [oracle_bootstrap.BootstrapSuite._structural_error(p) for p in proposals]
            malformed = [reason for reason in malformed if reason]
            if malformed:
                raise ValueError(
                    f"proposed_predicates contains {len(malformed)} unusable entr(ies): "
                    f"{malformed[0]} — a reviewer's proposals must be mechanically evaluable")
            # a declaration must be the boolean true, not any truthy value: the
            # string "false" is not an honest declaration
            declared = response.get("not_mechanically_checkable") is True
            if not (proposals or declared):
                raise ValueError(
                    "an APPROVE from a strong reviewer must carry proposed_predicates "
                    "(mechanically evaluable) or not_mechanically_checkable=true with reasons — "
                    "judge opinion alone never certifies a dimension")
        record["response"] = response
        record["status"] = "answered"
        return record

    def open_escalations(self, trigger: str | None = None) -> list[dict]:
        rows = [e for e in self.data["escalations"] if e["status"] == "open"]
        return [e for e in rows if trigger is None or e["trigger"] == trigger]

    def answered(self, trigger: str) -> list[dict]:
        return [e for e in self.data["escalations"]
                if e["trigger"] == trigger and e["status"] == "answered"]

    # -- T1: task start --------------------------------------------------------------

    def assess_task_start(self, signals: dict) -> dict | None:
        """signals: {files_planned: int, protected_touched: bool,
        unverified_share: float, symptom_families: int}"""
        if not self.policy["enabled"] or not self.policy.get("council_enabled", False):
            return None
        limits = self.policy["complexity"]
        hits = []
        if signals.get("files_planned", 0) > limits["max_files"]:
            hits.append("files")
        if signals.get("protected_touched"):
            hits.append("protected")
        if signals.get("unverified_share", 0.0) > limits["max_unverified_share"]:
            hits.append("unverified-share")
        if signals.get("symptom_families", 0) > limits["max_symptom_families"]:
            hits.append("symptom-families")
        if not hits:
            return None
        return self._open("T1-task-start", "council",
                          {"signals": signals, "hits": hits})

    # -- T3/T5: loop observation ------------------------------------------------------

    def observe_iterations(self, iterations: list[dict]) -> dict | None:
        """iterations: the campaign/daily loop's records, each with
        failure_fingerprint and failing family ids (if graded)."""
        if not self.policy["enabled"] or len(iterations) < 2:
            return None
        last, previous = iterations[-1], iterations[-2]
        if (last.get("failure_fingerprint") and
                last.get("failure_fingerprint") == previous.get("failure_fingerprint")):
            if not any(e["trigger"] == "T3-stall" and
                       e["payload"].get("fingerprint") == last["failure_fingerprint"]
                       for e in self.data["escalations"]):
                # a stall escalates to the council when it is enabled, and
                # degrades to a single strong review when it is not — the stall
                # is real either way (measured: an era trial froze at 57)
                kind = "council" if self.policy.get("council_enabled", False) else "review"
                return self._open("T3-stall", kind,
                                  {"fingerprint": last["failure_fingerprint"],
                                   "iteration": len(iterations)})
        family_counts: dict[str, int] = {}
        for iteration in iterations:
            for family in iteration.get("failing_families", []):
                family_counts[family] = family_counts.get(family, 0) + 1
        repeat_offenders = sorted(f for f, n in family_counts.items()
                                  if n >= self.policy["family_red_repeats"])
        already = {e["payload"].get("family") for e in self.data["escalations"]
                   if e["trigger"] == "T5-family-repeat"}
        for family in repeat_offenders:
            if family not in already:
                return self._open("T5-family-repeat", "review", {"family": family})
        return None

    # -- T2: pre-done -----------------------------------------------------------------

    def pre_done(self, unverified_dimensions: list[str]) -> dict:
        """Returns {'ready': bool, ...}. The gate calls this; with unverified
        dimensions present, done REQUIRES an answered T2 review covering them."""
        if not self.policy["enabled"] or not unverified_dimensions:
            return {"ready": True, "reason": "no named-unverified dimensions"}
        for record in self.answered("T2-pre-done"):
            covered = set(record["payload"].get("dimensions", []))
            response = record.get("response") or {}
            if response.get("verdict") != "approve":
                # A reviewer who blocked or asked for changes has NOT cleared the
                # gate. Answeredness is not agreement — the objection must cost
                # something or the whole tier is theatre.
                continue
            if set(unverified_dimensions) <= covered:
                return {"ready": True,
                        "reason": "strong review recorded — process unblocked",
                        "escalation_index": record["index"],
                        # the review NEVER certifies: the manifest keeps these
                        # dimensions typed as reviewed-unverified, and any
                        # predicates the reviewer proposed still face admission
                        "manifest_provenance": REVIEW_PROVENANCE,
                        "dimensions_reviewed_not_verified": sorted(unverified_dimensions),
                        "proposed_predicates": response.get("proposed_predicates", []),
                        "human_acceptance_required": bool(
                            response.get("not_mechanically_checkable"))}
        record = next((e for e in self.open_escalations("T2-pre-done")
                       if set(unverified_dimensions) <= set(e["payload"].get("dimensions", []))),
                      None)
        if record is None:
            record = self._open("T2-pre-done", "review",
                                {"dimensions": sorted(unverified_dimensions)})
        return {"ready": False,
                "reason": "NAMED-unverified dimensions require a recorded strong-model review "
                          "before done — mechanical dimensions stay mechanical",
                "escalation_index": record["index"]}

    # -- T4: risk gate ----------------------------------------------------------------

    def risk_gate(self, protected_touched: bool, mode_critical: bool) -> dict | None:
        if not self.policy["enabled"] or not (protected_touched or mode_critical):
            return None
        if self.answered("T4-risk"):
            return None
        existing = self.open_escalations("T4-risk")
        if existing:
            return existing[0]
        return self._open("T4-risk", "review",
                          {"protected_touched": protected_touched,
                           "mode_critical": mode_critical})

    # -- budgeted self-request ---------------------------------------------------------

    def support(self, brief: dict) -> dict:
        if not self.policy["enabled"]:
            return {"granted": False, "reason": "the tiered policy is disabled for this task"}
        missing = [f for f in REQUIRED_BRIEF_FIELDS if not str(brief.get(f, "")).strip()]
        if missing:
            return {"granted": False,
                    "reason": f"brief incomplete (missing: {', '.join(missing)}) — the brief IS "
                              "the filter; write it properly"}
        if self.data["support_spent"] >= self.policy["support_budget"]:
            return {"granted": False,
                    "reason": f"support budget exhausted "
                              f"({self.policy['support_budget']} per task)"}
        self.data["support_spent"] += 1
        # a self-request cannot smuggle the council in through the back door:
        # with the council tier off it is served by a single strong review
        kind = "council" if self.policy.get("council_enabled", False) else "review"
        record = self._open("self-request", kind, {"brief": brief})
        return {"granted": True, "escalation_index": record["index"], "kind": kind,
                "remaining": self.policy["support_budget"] - self.data["support_spent"]}


def review_brief(escalation: dict, context: dict) -> str:
    """The single-strong-reviewer brief (T2/T4/T5 and the ladder's first rung)."""
    return (
        "You are the STRONG REVIEWER in a tiered loop. A weaker executor did the work; mechanical "
        "predicates verified what they can. You review ONLY what they cannot see.\n\n"
        f"TRIGGER: {escalation['trigger']}\nPAYLOAD: {json.dumps(escalation['payload'], ensure_ascii=False)}\n\n"
        f"CONTEXT:\n{json.dumps(context, ensure_ascii=False)[:6000]}\n\n"
        "Reply with ONLY a JSON object:\n"
        '{"verdict": "approve|block|revise", "reasons": ["..."], '
        '"required_changes": ["..."], '
        '"proposed_predicates": [<predicates in the bootstrap shapes — relation kinds-superset / '
        'count-direction / count-equal — for EVERY countable consequence you checked>], '
        '"not_mechanically_checkable": <true only if nothing you reviewed has a countable '
        'observable>, "not_checkable_reasons": ["..."]}\n\n'
        "TWO HARD RULES, both from measurement:\n"
        "  1. Your APPROVE does not certify anything. Reported judge pass rates run 0.72-0.94 "
        "where true accuracy is 0.20, and ensembling judges does not fix it. So an approve is "
        "REFUSED unless it carries proposed_predicates or an explicit not_mechanically_checkable "
        "declaration — you leave behind machinery or you leave behind an honest 'a human must "
        "accept this'.\n"
        "  2. Every predicate you propose is mechanically admitted or REJECTED (it must fail on "
        "the pre-work baseline). Proposing something the old code already satisfies is a "
        "recorded miss, not a contribution."
    )
