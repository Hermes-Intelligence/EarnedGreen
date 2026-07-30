#!/usr/bin/env python3
"""Notes-as-code: the institutional learning loop, with earned persistence.

WHY. Two measured facts forced this design:

  * P1 was falsified (evidence/step7-P1-verdict.json): a clean-context author
    misses or under-grounds the hardest dimension, three trials out of three,
    three failure modes out of three. The agents' errors REPEAT.
  * Knowledge delivered as prose measured inert (vanilla-configured = loop =
    vanilla on correctness). The only artifacts that ever moved an outcome were
    EXECUTABLE (differentials, admitted checks, gates).

So the environment learns between sessions the only way our own data says
works: an observed error becomes a NOTE — the smallest unit of institutional
memory — that is routed into the next agent's context at the moment it is
relevant (the author's brief, not a wiki), and whose right to persist is
EARNED, exactly like a check's right to be green:

  observe a real error -> draft a note (error CLASS, never a task's answer)
    -> verify it transfers (a measured test: does the next agent stop making
       this class of error?) -> route it forward -> RETIRE it when it stops
       discriminating or its premise dies.

THE RULE THAT KEEPS THE BANK HONEST is the vacuity rule one level up. Memory
systems die of rot: stale, vague, unfalsifiable advice accumulating until
agents ignore all of it. Here every note must state, at write time:
  * `applies_when` — routing, so it is injected only where it is relevant;
  * `verification`  — how we know it transfers (status starts `provisional`;
    only a recorded measurement upgrades it to `measured`);
  * `retire_when`   — the observable condition under which the note is WRONG
    or obsolete. A note that cannot say how it would die is not knowledge,
    it is superstition, and the schema rejects it.

Notes complement checks, not replace them: a check catches an error after it
is made; a note lowers the probability it is made at all — and teaches the
author to write the check that catches it. Zero provider calls in this module;
measurement spends live in the campaign runner where approval does.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DEFAULT_BANK = HERE / "notes" / "bank.json"

_AUDIENCES = {"check-author", "implementer", "reviewer", "any"}
_STATUSES = {"provisional", "measured", "retired"}
_REQUIRED = ("id", "error_class", "audience", "lesson", "how_to_apply",
             "provenance", "verification", "retire_when")


class NoteError(ValueError):
    """A malformed note never enters the bank: rot prevention starts at write."""


def validate_note(note: dict[str, Any]) -> None:
    for field in _REQUIRED:
        value = note.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            raise NoteError(f"note {note.get('id')!r} is missing `{field}`: a note that cannot state "
                            "its routing, its evidence and its death condition is superstition, not knowledge")
    if not isinstance(note["audience"], list) or not note["audience"]:
        raise NoteError(f"note {note['id']!r}: `audience` must be a non-empty list")
    unknown = set(note["audience"]) - _AUDIENCES
    if unknown:
        raise NoteError(f"note {note['id']!r} names unknown audience {sorted(unknown)}; "
                        f"known: {sorted(_AUDIENCES)}")
    status = (note["verification"] or {}).get("status")
    if status not in _STATUSES:
        raise NoteError(f"note {note['id']!r}: verification.status must be one of {sorted(_STATUSES)}")
    if status == "measured" and not (note["verification"] or {}).get("records"):
        raise NoteError(f"note {note['id']!r} claims `measured` with no measurement records: "
                        "an unrecorded measurement is a claim, and claims are `provisional`")
    provenance = note["provenance"]
    if not isinstance(provenance, dict) or not (provenance.get("observed_in") and provenance.get("observed_at")):
        raise NoteError(f"note {note['id']!r}: provenance must name `observed_in` (runs/evidence) and "
                        "`observed_at`: a lesson nobody actually observed is a guess wearing a badge")


def load_bank(path: Path | None = None) -> dict[str, Any]:
    path = Path(path or DEFAULT_BANK)
    if not path.is_file():
        return {"schema_version": 1, "notes": []}
    bank = json.loads(path.read_text(encoding="utf-8-sig"))
    seen: set[str] = set()
    for note in bank.get("notes", []):
        validate_note(note)
        if note["id"] in seen:
            raise NoteError(f"duplicate note id {note['id']!r}")
        seen.add(note["id"])
    return bank


def save_bank(bank: dict[str, Any], path: Path | None = None) -> Path:
    path = Path(path or DEFAULT_BANK)
    for note in bank.get("notes", []):
        validate_note(note)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bank, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def relevant_notes(bank: dict[str, Any], audience: str,
                   context_tags: set[str] | None = None) -> list[dict[str, Any]]:
    """Route: active notes for this audience whose tags overlap the context.

    Retired notes never route (that is what retirement MEANS), and a note with
    `applies_when.tags` routes only into a context sharing at least one tag —
    injecting every note everywhere is how banks train agents to skim.
    """
    rows = []
    for note in bank.get("notes", []):
        if note["verification"]["status"] == "retired":
            continue
        if audience not in note["audience"] and "any" not in note["audience"]:
            continue
        tags = set((note.get("applies_when") or {}).get("tags") or [])
        if tags and context_tags is not None and not (tags & context_tags):
            continue
        rows.append(note)
    return rows


def render_for_brief(notes: list[dict[str, Any]]) -> str:
    """The routed notes, as a brief section the receiving agent acts on.

    Deliberately shows verification status: an agent deserves to know whether a
    lesson is measured or provisional, the same way a reader deserves to know
    a result's n. Lessons are stated as error CLASSES with an action — never as
    any task's answer.
    """
    if not notes:
        return ""
    lines = [
        "LESSONS FROM PRIOR FAILURES IN THIS ENVIRONMENT",
        "Real agents doing real work here made the errors below. Each lesson was drafted from an",
        "observed failure and carries its verification status. Apply them; they override habit.",
        "",
    ]
    for note in notes:
        status = note["verification"]["status"]
        lines.append(f"* [{note['error_class']}] ({status}) {note['lesson'].strip()}")
        lines.append(f"  How to apply: {note['how_to_apply'].strip()}")
    return "\n".join(lines)


def record_measurement(bank: dict[str, Any], note_id: str, record: dict[str, Any]) -> None:
    """Attach a measurement and settle the status it earns.

    `transferred: true` upgrades provisional -> measured. `transferred: false`
    RETIRES the note: a lesson that demonstrably does not change the next
    agent's behaviour is exactly the rot this bank exists to refuse.
    """
    note = next((row for row in bank.get("notes", []) if row["id"] == note_id), None)
    if note is None:
        raise NoteError(f"unknown note id {note_id!r}")
    if "transferred" not in record or "evidence" not in record:
        raise NoteError("a measurement record must state `transferred` (bool) and `evidence`")
    note["verification"].setdefault("records", []).append(
        dict(record, recorded_at=datetime.now(timezone.utc).isoformat()))
    note["verification"]["status"] = "measured" if record["transferred"] else "retired"
    if not record["transferred"]:
        note["verification"]["retired_reason"] = "measured non-transfer: the lesson did not change behaviour"


def draft_from_campaign(campaign: dict[str, Any]) -> list[dict[str, Any]]:
    """Capture: turn a campaign's failure->fix pairs into CANDIDATE notes.

    Every loop iteration that went red and later green is an observed
    error-and-recovery. The draft is deliberately a skeleton — `lesson` and
    `how_to_apply` must be written by whoever (agent or owner) understands the
    failure CLASS, then pass validate_note. Auto-generated prose would be the
    exact vague rot the bank refuses; the capture's job is to make sure no
    observed error is silently forgotten, not to pretend it understands it.
    """
    drafts: list[dict[str, Any]] = []
    for entry in campaign.get("runs", []):
        iterations = entry.get("iterations") or []
        for index, row in enumerate(iterations):
            if row.get("green") or not row.get("failing_check_ids"):
                continue
            recovered = any(later.get("green") for later in iterations[index + 1:])
            drafts.append({
                "id": f"DRAFT-{entry.get('run_id', 'run')}-i{row.get('iteration')}",
                "error_class": "TODO-name-the-class",
                "audience": ["check-author"],
                "applies_when": {"tags": []},
                "lesson": "TODO: state the error CLASS (never this task's answer)",
                "how_to_apply": "TODO: the action the next agent takes instead",
                "provenance": {
                    "observed_in": [entry.get("run_id")],
                    "observed_at": datetime.now(timezone.utc).date().isoformat(),
                    "failing_check_ids": row.get("failing_check_ids"),
                    "recovered_later": recovered,
                },
                "verification": {"status": "provisional", "records": []},
                "retire_when": "TODO: the observable condition under which this lesson is wrong or obsolete",
            })
    return drafts


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description="Inspect and maintain the notes bank (zero provider calls).")
    sub = parser.add_subparsers(dest="action", required=True)
    show = sub.add_parser("show", help="validate and list the bank")
    show.add_argument("--bank", type=Path)
    route = sub.add_parser("route", help="what a given audience/context would receive")
    route.add_argument("--bank", type=Path)
    route.add_argument("--audience", required=True)
    route.add_argument("--tags", default="", help="comma-separated context tags")
    capture = sub.add_parser("capture", help="draft candidate notes from a campaign's failure/fix pairs")
    capture.add_argument("--campaign", type=Path, required=True)
    capture.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.action == "show":
        bank = load_bank(args.bank)
        for note in bank["notes"]:
            print(f"{note['id']} [{note['error_class']}] {note['verification']['status']}")
        print(f"total: {len(bank['notes'])}")
        return
    if args.action == "route":
        bank = load_bank(args.bank)
        tags = {tag.strip() for tag in args.tags.split(",") if tag.strip()} or None
        rendered = render_for_brief(relevant_notes(bank, args.audience, tags))
        print(rendered or "(no notes route to this context)")
        return
    campaign = json.loads(args.campaign.read_text(encoding="utf-8-sig"))
    drafts = draft_from_campaign(campaign)
    args.output.write_text(json.dumps({"drafts": drafts}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(drafts)} candidate note(s) drafted -> {args.output}")


if __name__ == "__main__":
    main()
