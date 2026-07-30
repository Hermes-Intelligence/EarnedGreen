#!/usr/bin/env python3
"""Briefs for the declared support roles — the execution half of a strategy.

`execution_strategy` says WHO checks the work; this turns that record into
files a session can actually dispatch: one adversarial brief for the reviewer,
one independent-lens brief per council member. The driving agent (or a campaign
runner) spawns a subagent per brief with the model the record resolved.

Two deliberate choices, both paid for elsewhere in this programme:

  The reviewer brief leads with COMPLETENESS, not style. The one measured trial
  of the reviewed arm produced the best-formatted deliverable and silently
  dropped three of four checkable figures — polish is what reviewers notice
  unprompted, so the brief points the other way.

  Council members get DIFFERENT lenses and an explicit no-coordination line.
  Independent panels amplify errors 17.2x when they echo each other; the value
  of a second reader is exactly the places it disagrees.
"""
from __future__ import annotations

from pathlib import Path

REVIEWER_BRIEF = """# Reviewer brief (adversarial)

Model for this role: **{selector}** (profile {profile}).

You are reviewing work you did NOT write, with fresh context. Your job is to
find what is WRONG, not to admire what is right: missing behaviours, numbers
that do not trace to a source, claims the diff does not support, states
(loading / empty / error / mobile) that were never handled.

The one measured failure of this role's arm: polish went up while THREE OF FOUR
checkable figures were silently dropped. Check completeness FIRST, style second.

## The task the work was meant to do

{task}

Return findings as a list: claim, where you looked, what you expected, what you
found. "Looks good" with no location examined is not a finding.
"""

COUNCIL_BRIEF = """# Council brief {index} (independent perspective)

Model for this role: **{selector}** (profile {profile}).

You have NOT seen any other council member's brief and must not coordinate.
Your lens: {lens}

## The task

{task}

Independent panels amplify errors 17.2x when they echo each other; your value is
exactly the places you DISAGREE with the work. Return a ranked list.
"""

LENSES = [
    "What is the strongest DIFFERENT design that was not chosen, and does its "
    "existence reveal a weakness in this one?",
    "Where will this age badly: what breaks when the next client, the next "
    "endpoint, the next screen size arrives?",
    "What would a hostile expert quote from this work in a takedown, and would "
    "they be right?",
]


def emit(record: dict, task_text: str, out_dir: Path) -> list[tuple[str, str, str]]:
    """Write one brief per declared support role. Returns (role, model, filename)."""
    roles = record.get("models", {}).get("roles", {})
    council = record.get("models", {}).get("council") or []
    out_dir.mkdir(parents=True, exist_ok=True)
    emitted: list[tuple[str, str, str]] = []

    reviewer = roles.get("reviewer")
    if reviewer:
        path = out_dir / "reviewer-brief.md"
        path.write_text(REVIEWER_BRIEF.format(selector=reviewer.get("selector"),
                                              profile=reviewer.get("profile"),
                                              task=task_text.strip() or "(no task text found)"),
                        encoding="utf-8")
        emitted.append(("reviewer", str(reviewer.get("selector")), path.name))

    for index, member in enumerate(council):
        path = out_dir / f"council-brief-{index + 1}.md"
        path.write_text(COUNCIL_BRIEF.format(index=index + 1,
                                             selector=member.get("selector"),
                                             profile=member.get("profile"),
                                             lens=LENSES[index % len(LENSES)],
                                             task=task_text.strip() or "(no task text found)"),
                        encoding="utf-8")
        emitted.append((f"council_{index + 1}", str(member.get("selector")), path.name))
    return emitted
