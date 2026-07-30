#!/usr/bin/env python3
"""Spec-first planning phase: scaffold, validate and freeze a task specification.

For an UNDERSPECIFIED task (clarity axis), the agent must explore the workspace
and produce a spec BEFORE implementation. The spec is generative, not a checklist:

  * surface_inventory  - the task's actual surfaces, enumerated from the code
                         (external I/O, persistence, state/concurrency, parsers,
                         contracts/consumers, caches, ordering, config - a
                         starting lens, `kind` is free-form and open-world);
  * convention_inventory - implicit house conventions discovered in the repo,
                         each citing a real file;
  * decision_points    - every material interpretation choice, pinned by
                         evidence or explicitly escalated to the owner (which
                         BLOCKS completion until resolved);
  * risk_register      - risks traced to surfaces or requirements, each with a
                         mitigation and a runnable verification;
  * rejected_approaches - approaches considered and dropped, so they are not
                         silently redone;
  * acceptance_tests   - self-verifying commands (exit 0 iff the expectation
                         holds) that the completion gate re-executes;
  * frozen_ledger      - the union of task-text requirements (from
                         objective_compiler) and spec-discovered requirements.

`validate` is fail-closed and emits `spec_sha256` over the canonicalized frozen
ledger + acceptance tests. With `--freeze`, the first PASS records the freeze;
afterwards any removal, rewrite or downgrade of a frozen row without an explicit
`owner_scope_change` entry (human approval string + reason) is a violation.
Additions are always allowed: scope may grow, never silently shrink.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

from objective_compiler import compile_ledger

SCHEMA_VERSION = 1
_LEDGER_SOURCES = {"task-text", "discovered"}
_DOWNGRADED = {"not_applicable", "rejected"}

ADVERSARIAL_INSTRUCTIONS = (
    "Separate pass over ONLY the task, the workspace and this filled spec. Hunt for: "
    "(a) a decision point that is unpinned or pinned without evidence, "
    "(b) a surface present in the code but missing from surface_inventory, "
    "(c) a risk whose verification is not a real, runnable demonstration. "
    "Any finding blocks the spec until resolved. The reviewer is not bound by any "
    "category list; novel failure modes are expected."
)


def normalized(value: str) -> str:
    return re.sub(r"\s+", " ", str(value).strip()).lower()


def spec_freeze_sha256(spec: dict[str, Any]) -> str:
    """Freeze hash over the canonicalized frozen ledger + acceptance tests."""
    rows = sorted(
        (
            {"id": row.get("id"), "statement": normalized(row.get("statement", "")), "source": row.get("source")}
            for row in spec.get("frozen_ledger", {}).get("requirements", [])
        ),
        key=lambda row: str(row["id"]),
    )
    tests = sorted(
        (
            {"id": test.get("id"), "command": test.get("command"), "expected": test.get("expected")}
            for test in spec.get("acceptance_tests", [])
        ),
        key=lambda test: str(test["id"]),
    )
    payload = json.dumps({"frozen_ledger": rows, "acceptance_tests": tests},
                         sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest().upper()


def compile_spec(task: str, task_source: str) -> dict[str, Any]:
    """Produce the spec SCAFFOLD the agent must fill by exploring the workspace."""
    ledger = compile_ledger(task, task_source)
    requirements = [
        {"id": row["id"], "statement": row["statement"], "source": "task-text", "status": "pending"}
        for row in ledger["requirements"]
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "scaffold",
        "task_source": task_source,
        "task_sha256": ledger["task_sha256"],
        "objective_restatement": "",
        "surface_inventory": [],
        "convention_inventory": [],
        "decision_points": [],
        "risk_register": [],
        "rejected_approaches": [],
        "acceptance_tests": [],
        "coverage_argument": "",
        "adversarial_review": {"status": "pending", "reviewed_by": None,
                               "instructions": ADVERSARIAL_INSTRUCTIONS, "findings": []},
        "frozen_ledger": {"requirements": requirements, "owner_scope_changes": []},
    }


def render_spec_md(spec: dict[str, Any]) -> str:
    lines = [
        "# Task specification (spec-first contract)",
        "",
        "This task was classified UNDERSPECIFIED: its real requirements live in the",
        "codebase's implicit conventions, not in the task text. Before ANY mutation:",
        "",
        "1. Explore the workspace. Read the modules the change will touch AND the",
        "   modules that consume them; read docstrings - house conventions hide there.",
        "2. Fill every section of `spec.json`:",
        "   - `objective_restatement`: the task in your own words, full scope.",
        "   - `surface_inventory`: THIS task's real surfaces, derived from the code,",
        "     each `{id, kind, surface, evidence_file}`. Kinds are open-world",
        "     (external I/O, persistence, state/concurrency, parsers, contracts,",
        "     caches, ordering, config are a starting lens, never the universe).",
        "   - `convention_inventory`: `{convention, source_file_or_evidence,",
        "     applies_because}` - implicit rules the code already follows.",
        "   - `decision_points`: `{id, question, options, pinned_choice, pinned_by}`;",
        "     pin by evidence, or set `owner_decision_required: true` (blocks).",
        "   - `risk_register`: `{id, risk, likelihood, surface_id|requirement_id,",
        "     mitigation, verification}` - every surface needs a risk or a reasoned",
        "     `not_applicable_reason`; read `risk-discovery.md` for failure modes",
        "     that really happened (illustrative, never exhaustive).",
        "   - `rejected_approaches`: what you considered and dropped, and why.",
        "   - `acceptance_tests`: `{id, command, expected}` - self-verifying commands",
        "     (exit 0 iff the expectation holds); the completion gate re-executes them.",
        "   - `coverage_argument`: why you believe the inventory is complete for this",
        "     task and what was deliberately left out.",
        "   - `frozen_ledger.requirements`: ADD every spec-discovered requirement with",
        "     `source: \"discovered\"`. Never remove task-text rows.",
        "3. Run the adversarial review described in `spec.json` and set its status.",
        "4. Validate and freeze:",
        "   `python .agentic/spec_synthesis.py validate --spec .agentic/spec.json`",
        "   ` --workspace . --task-file <task> --freeze .agentic/spec-freeze.json`",
        "",
        "The freeze is the anti-scope-shrink boundary: completion means the FULL",
        "frozen scope passes its acceptance tests. Removing or downgrading a frozen",
        "requirement without an `owner_scope_changes` entry (a human approval string",
        "plus reason) fails the pre-submit gate. Additions are always allowed.",
        "",
        f"Task source: {spec.get('task_source')}",
        f"Task sha256: {spec.get('task_sha256')}",
        "",
        "## Task-text requirements already compiled into the frozen ledger",
        "",
    ]
    for row in spec.get("frozen_ledger", {}).get("requirements", []):
        lines.append(f"- `{row['id']}` {row['statement']}")
    lines.append("")
    return "\n".join(lines)


def _approved_scope_changes(spec: dict[str, Any]) -> set[str]:
    return {
        row.get("requirement_id")
        for row in spec.get("frozen_ledger", {}).get("owner_scope_changes", [])
        if str(row.get("approved_by", "")).strip() and str(row.get("reason", "")).strip()
    }


def validate_spec(spec: dict[str, Any], workspace: Path, task_text: str | None) -> dict[str, Any]:
    """Fail-closed structural + traceability validation of a filled spec."""
    failures: list[dict[str, str]] = []

    def fail(fid: str, reason: str) -> None:
        failures.append({"id": fid, "reason": reason})

    workspace = Path(workspace)
    if spec.get("schema_version") != SCHEMA_VERSION:
        fail("spec-schema", f"schema_version must be {SCHEMA_VERSION}")
    if not str(spec.get("objective_restatement") or "").strip():
        fail("objective-restatement", "empty: restate the full objective in your own words")

    # Decision points: pinned by evidence, or explicitly escalated (which blocks).
    for point in spec.get("decision_points", []):
        pid = str(point.get("id") or "<missing-id>")
        pinned_by = str(point.get("pinned_by") or "").strip()
        if point.get("owner_decision_required") or pinned_by.lower() == "owner-decision-required":
            fail(f"decision:{pid}", "owner decision required and unresolved: completion is blocked until the owner pins this choice")
            continue
        if len(point.get("options") or []) < 2:
            fail(f"decision:{pid}", "fewer than two options were considered")
        if not str(point.get("pinned_choice") or "").strip():
            fail(f"decision:{pid}", "no pinned_choice")
        if not pinned_by:
            fail(f"decision:{pid}", "pinned_choice has no evidence (pinned_by)")

    # Surface inventory: derived from the code, evidence-cited, open-world kinds.
    surfaces = spec.get("surface_inventory") or []
    if not surfaces:
        fail("surface-inventory", "empty: enumerate this task's real surfaces from the workspace")
    surface_ids: set[str] = set()
    for surface in surfaces:
        sid = str(surface.get("id") or "").strip()
        if not sid or sid in surface_ids:
            fail("surface-inventory", f"missing or duplicate surface id: {sid!r}")
            continue
        surface_ids.add(sid)
        if not str(surface.get("kind") or "").strip() or not str(surface.get("surface") or "").strip():
            fail(f"surface:{sid}", "surface entries need a free-form kind and a description")
        evidence_file = str(surface.get("evidence_file") or "").strip()
        if not evidence_file or not (workspace / evidence_file).exists():
            fail(f"surface:{sid}", f"evidence_file missing or not found in workspace: {evidence_file!r}")

    # Risk register: traceability, not coverage-of-a-list.
    ledger_rows = spec.get("frozen_ledger", {}).get("requirements", [])
    ledger_ids = {row.get("id") for row in ledger_rows}
    risk_texts: set[str] = set()
    surfaces_with_risk: set[str] = set()
    for index, risk in enumerate(spec.get("risk_register", [])):
        rid = str(risk.get("id") or f"risk-{index}")
        text = normalized(risk.get("risk") or "")
        if not text:
            fail(f"risk:{rid}", "empty risk statement")
        elif text in risk_texts:
            fail(f"risk:{rid}", "duplicate risk statement: template boilerplate is not analysis")
        risk_texts.add(text)
        if not str(risk.get("mitigation") or "").strip():
            fail(f"risk:{rid}", "no mitigation")
        if not str(risk.get("verification") or "").strip():
            fail(f"risk:{rid}", "no verification: how will this risk's absence be demonstrated?")
        if risk.get("surface_id") in surface_ids:
            surfaces_with_risk.add(risk["surface_id"])
        elif risk.get("requirement_id") not in ledger_ids:
            fail(f"risk:{rid}", "does not trace to a surface_inventory id or a frozen_ledger requirement id")
    for surface in surfaces:
        sid = surface.get("id")
        if sid in surfaces_with_risk:
            continue
        if not str(surface.get("not_applicable_reason") or "").strip():
            fail(f"surface:{sid}", "no risk_register entry and no reasoned not_applicable_reason")
    if not str(spec.get("coverage_argument") or "").strip():
        fail("coverage-argument", "missing: state why the surface inventory is believed complete for this task and what was deliberately left out")

    # Convention inventory: every entry cites real, existing evidence.
    conventions = spec.get("convention_inventory") or []
    if not conventions:
        fail("convention-inventory", "empty: record the house conventions this change must respect")
    for index, convention in enumerate(conventions):
        cid = f"convention-{index}"
        if not str(convention.get("convention") or "").strip():
            fail(cid, "empty convention")
        source = str(convention.get("source_file_or_evidence") or "").strip()
        if not source:
            fail(cid, "no source_file_or_evidence")
        elif not (workspace / source.split("::", 1)[0]).exists():
            fail(cid, f"evidence file not found in workspace: {source.split('::', 1)[0]!r}")
        if not str(convention.get("applies_because") or "").strip():
            fail(cid, "no applies_because")

    # Rejected approaches: structural only; the section may be empty.
    for index, rejected in enumerate(spec.get("rejected_approaches", [])):
        if not str(rejected.get("approach") or "").strip() or not str(rejected.get("why_rejected") or "").strip():
            fail(f"rejected-approach-{index}", "entries need approach and why_rejected")

    # Acceptance tests: runnable, self-verifying commands.
    tests = spec.get("acceptance_tests") or []
    if not tests:
        fail("acceptance-tests", "empty: the spec must name runnable commands that validate the frozen scope")
    seen_tests: set[str] = set()
    for test in tests:
        tid = str(test.get("id") or "").strip()
        if not tid or tid in seen_tests:
            fail("acceptance-tests", f"missing or duplicate acceptance test id: {tid!r}")
            continue
        seen_tests.add(tid)
        command = test.get("command")
        runnable = (isinstance(command, str) and command.strip()) or (
            isinstance(command, list) and command and all(isinstance(token, str) and token for token in command))
        if not runnable:
            fail(f"acceptance:{tid}", "no runnable command")
        if not str(test.get("expected") or "").strip():
            fail(f"acceptance:{tid}", "no expected outcome stated")

    # Frozen ledger: non-empty, sourced, and NO task-text requirement dropped.
    if not ledger_rows:
        fail("frozen-ledger", "empty frozen ledger")
    for row in ledger_rows:
        if row.get("source") not in _LEDGER_SOURCES:
            fail(f"ledger:{row.get('id')}", "source must be task-text or discovered")
    if task_text is None:
        fail("frozen-ledger", "task text unavailable: cannot verify that no task-text requirement was silently dropped")
    else:
        compiled = compile_ledger(task_text)["requirements"]
        for req in compiled:
            if req["id"] not in ledger_ids:
                fail("frozen-ledger", f"task-text requirement silently dropped: {req['id']} ({req['statement'][:80]!r})")

    # Adversarial review: a separate pass, not bound by any list.
    review = spec.get("adversarial_review") or {}
    if review.get("status") != "clear":
        fail("adversarial-review", "adversarial spec review is not clear: " + ADVERSARIAL_INSTRUCTIONS)
    elif not str(review.get("reviewed_by") or "").strip():
        fail("adversarial-review", "no reviewed_by recorded for the adversarial pass")
    for index, finding in enumerate(review.get("findings", [])):
        if not str(finding.get("resolution") or "").strip():
            fail(f"adversarial-finding-{index}", "unresolved adversarial finding blocks the spec")

    return {
        "schema_version": SCHEMA_VERSION,
        "verdict": "PASS" if not failures else "FAIL",
        "failures": failures,
        "spec_sha256": spec_freeze_sha256(spec),
    }


def freeze_record(spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "spec_sha256": spec_freeze_sha256(spec),
        "requirements": [
            {"id": row.get("id"), "statement": row.get("statement"), "source": row.get("source")}
            for row in spec.get("frozen_ledger", {}).get("requirements", [])
        ],
        "acceptance_tests": [
            {"id": test.get("id"), "command": test.get("command"), "expected": test.get("expected")}
            for test in spec.get("acceptance_tests", [])
        ],
    }


def freeze_violations(spec: dict[str, Any], freeze: dict[str, Any]) -> list[str]:
    """Anti-scope-shrink: every frozen row must survive; additions are allowed."""
    current = {row.get("id"): row for row in spec.get("frozen_ledger", {}).get("requirements", [])}
    approved = _approved_scope_changes(spec)
    violations: list[str] = []
    for row in freeze.get("requirements", []):
        rid = row.get("id")
        live = current.get(rid)
        if live is None:
            if rid not in approved:
                violations.append(f"frozen requirement {rid} was removed without an owner_scope_change entry")
            continue
        if normalized(live.get("statement", "")) != normalized(row.get("statement", "")) and rid not in approved:
            violations.append(f"frozen requirement {rid} statement was rewritten without an owner_scope_change entry")
        if live.get("status") in _DOWNGRADED and rid not in approved:
            violations.append(f"frozen requirement {rid} downgraded to {live.get('status')!r} without an owner_scope_change entry")
    live_tests = {test.get("id"): test for test in spec.get("acceptance_tests", [])}
    for test in freeze.get("acceptance_tests", []):
        tid = test.get("id")
        live = live_tests.get(tid)
        if live is None:
            violations.append(f"frozen acceptance test {tid} was removed")
        elif live.get("command") != test.get("command"):
            violations.append(f"frozen acceptance test {tid} command was rewritten")
    return violations


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    compile_parser = sub.add_parser("compile", help="produce the spec scaffold for an underspecified task")
    source = compile_parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--task")
    source.add_argument("--task-file", type=Path)
    compile_parser.add_argument("--workspace", type=Path, required=True)
    compile_parser.add_argument("--output-dir", type=Path, help="defaults to <workspace>/.agentic")

    validate_parser = sub.add_parser("validate", help="fail-closed validation of a filled spec")
    validate_parser.add_argument("--spec", type=Path, required=True)
    validate_parser.add_argument("--workspace", type=Path, required=True)
    vsource = validate_parser.add_mutually_exclusive_group(required=True)
    vsource.add_argument("--task")
    vsource.add_argument("--task-file", type=Path)
    validate_parser.add_argument("--freeze", type=Path,
                                 help="freeze record path: written on first PASS, enforced afterwards")
    validate_parser.add_argument("--output", type=Path)

    args = parser.parse_args()
    if args.command == "compile":
        task = args.task if args.task is not None else args.task_file.read_text(encoding="utf-8-sig")
        spec = compile_spec(task, str(args.task_file or "inline-task"))
        output_dir = args.output_dir or (args.workspace / ".agentic")
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "spec.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (output_dir / "spec.md").write_text(render_spec_md(spec), encoding="utf-8")
        print(json.dumps({"status": "scaffold-written", "spec": str(output_dir / "spec.json"),
                          "task_text_requirements": len(spec["frozen_ledger"]["requirements"])},
                         ensure_ascii=False, indent=2))
        return

    spec = json.loads(args.spec.read_text(encoding="utf-8-sig"))
    task = args.task if args.task is not None else args.task_file.read_text(encoding="utf-8-sig")
    result = validate_spec(spec, args.workspace, task)
    if args.freeze:
        if args.freeze.is_file():
            freeze = json.loads(args.freeze.read_text(encoding="utf-8-sig"))
            for violation in freeze_violations(spec, freeze):
                result["failures"].append({"id": "spec-freeze", "reason": violation})
            result["verdict"] = "PASS" if not result["failures"] else "FAIL"
            result["freeze"] = {"path": str(args.freeze), "recorded_sha256": freeze.get("spec_sha256")}
        elif result["verdict"] == "PASS":
            record = freeze_record(spec)
            args.freeze.parent.mkdir(parents=True, exist_ok=True)
            args.freeze.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            result["freeze"] = {"path": str(args.freeze), "recorded_sha256": record["spec_sha256"]}
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    raise SystemExit(0 if result["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
