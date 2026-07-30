#!/usr/bin/env python3
"""SUPPORT COUNCIL — two strong models deliberate; the outcome ARMS THE ORACLE.

Protocol (all provider calls are made by the DRIVING session with its own
subagents — this module only builds briefs and validates responses):
  1. BLIND DRAFTS   two members, independently, same brief (forced diversity);
  2. CROSS-EXAM     each attacks the other's draft: what breaks, what is
                    lost, which edge cases, where it is not production-grade;
  3. DECISION MEMO  member A reconciles, member B countersigns or files a
                    dissent (dissent -> human gate).

The memo's INVARIANTS must be structured predicates in the bootstrap shapes.
Prose invariants are REJECTED by the validator: measured lesson — advice that
is not mechanically enforceable evaporates (findings-as-forms). Admitted
invariants join the loop's suite via oracle_bootstrap.admit_proposals
(provenance 'council'), so the weak executor is HELD to the council's
decisions for the rest of the task.
"""
from __future__ import annotations

import json
from typing import Any

MEMO_REQUIRED = ("approach", "risks", "do_nots", "invariants")


def draft_brief(task_context: dict, member_label: str) -> str:
    return (
        f"You are council member {member_label} — one of two senior engineers consulted "
        "INDEPENDENTLY (you do not see the other member). A weaker executor will implement this; "
        "your job is the approach that loses nothing and is production-grade.\n\n"
        f"TASK CONTEXT:\n{json.dumps(task_context, ensure_ascii=False)[:8000]}\n\n"
        "Reply with ONLY a JSON object:\n"
        '{"approach": "<the plan, concrete, stepwise>", '
        '"edge_cases": ["..."], "failure_modes": ["..."], '
        '"what_must_not_be_lost": ["..."]}'
    )


def cross_brief(own_draft: dict, other_draft: dict) -> str:
    return (
        "You are a council member in CROSS-EXAMINATION. Attack the OTHER member's plan as hard as "
        "you can: what breaks, what silently gets lost, which edge cases it misses, where it is "
        "not production-grade. Be specific; vague concerns are worthless.\n\n"
        f"YOUR OWN DRAFT (for reference):\n{json.dumps(own_draft, ensure_ascii=False)[:4000]}\n\n"
        f"THE OTHER MEMBER'S DRAFT (attack this):\n{json.dumps(other_draft, ensure_ascii=False)[:4000]}\n\n"
        'Reply with ONLY a JSON object: {"attacks": [{"target": "<which part>", '
        '"failure": "<concrete input/state -> wrong outcome>", "severity": "high|medium|low"}]}'
    )


def memo_brief(drafts: list[dict], attacks: list[dict]) -> str:
    return (
        "You are council member A, writing the RECONCILED DECISION MEMO from both drafts and both "
        "attack lists. Choose, merge, or synthesize — then commit.\n\n"
        f"DRAFTS:\n{json.dumps(drafts, ensure_ascii=False)[:6000]}\n\n"
        f"ATTACKS:\n{json.dumps(attacks, ensure_ascii=False)[:4000]}\n\n"
        "Reply with ONLY a JSON object:\n"
        '{"approach": "<the chosen plan>", "risks": ["..."], "do_nots": ["..."], '
        '"invariants": [<STRUCTURED PREDICATES ONLY, in the bootstrap shapes '
        '(relation kinds-superset / count-direction / count-equal, with input_id referring to the '
        "capture corpus). Every countable consequence of your decisions belongs here — an "
        "invariant that is not a predicate will be REJECTED and the executor will not be held to "
        'it.>], "notes_for_executor": ["<non-countable guidance, clearly secondary>"]}'
    )


def countersign_brief(memo: dict) -> str:
    return (
        "You are council member B. Member A wrote this reconciled decision memo. COUNTERSIGN it or "
        "file a dissent — a dissent halts the task for a human decision, so dissent only on "
        "substance.\n\n"
        f"MEMO:\n{json.dumps(memo, ensure_ascii=False)[:6000]}\n\n"
        'Reply with ONLY a JSON object: {"verdict": "countersign|dissent", "reasons": ["..."]}'
    )


def validate_memo(memo: Any) -> dict:
    """Schema gate for the reconciled memo. Prose invariants are rejected here,
    BEFORE admission even sees them."""
    if not isinstance(memo, dict):
        return {"valid": False, "reason": "memo is not an object"}
    missing = [f for f in MEMO_REQUIRED if f not in memo]
    if missing:
        return {"valid": False, "reason": f"memo missing fields: {', '.join(missing)}"}
    if not isinstance(memo["invariants"], list):
        return {"valid": False, "reason": "invariants must be a list"}
    prose = [i for i, inv in enumerate(memo["invariants"]) if not isinstance(inv, dict)]
    if prose:
        return {"valid": False,
                "reason": f"invariants at positions {prose} are prose — structured predicates only "
                          "(the findings-as-forms lesson, enforced)"}
    return {"valid": True, "invariant_count": len(memo["invariants"])}


def run_council(task_context: dict, responders: dict) -> dict:
    """Execute the whole protocol through injected responders:
    responders = {"member_a": fn(brief)->json-str, "member_b": fn(brief)->json-str}.
    In daily use the driving session provides these by spawning subagents; in
    benchmarks the runner injects them. Returns the validated memo package."""
    draft_a = json.loads(responders["member_a"](draft_brief(task_context, "A")))
    draft_b = json.loads(responders["member_b"](draft_brief(task_context, "B")))
    attack_ab = json.loads(responders["member_a"](cross_brief(draft_a, draft_b)))
    attack_ba = json.loads(responders["member_b"](cross_brief(draft_b, draft_a)))
    memo = json.loads(responders["member_a"](memo_brief([draft_a, draft_b],
                                                        [attack_ab, attack_ba])))
    validation = validate_memo(memo)
    if not validation["valid"]:
        return {"status": "invalid-memo", "validation": validation, "memo": memo}
    countersign = json.loads(responders["member_b"](countersign_brief(memo)))
    if countersign.get("verdict") != "countersign":
        return {"status": "dissent", "memo": memo, "dissent": countersign,
                "action": "HUMAN GATE: the council disagrees; a person decides"}
    return {"status": "agreed", "memo": memo, "countersign": countersign,
            "drafts": [draft_a, draft_b], "attacks": [attack_ab, attack_ba]}
