#!/usr/bin/env python3
"""Compile a compact, stable requirement ledger from a public task contract."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


def normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).lower()


def requirement_id(statement: str) -> str:
    return "REQ-TASK-" + hashlib.sha256(normalized(statement).encode("utf-8")).hexdigest()[:10].upper()


def evidence_types(statement: str) -> list[str]:
    text = statement.lower()
    kinds = {"behavior"}
    if any(term in text for term in ("test", "raise", "return", "accept", "reject", "preserve", "must not", "invalid")):
        kinds.add("test")
    if any(term in text for term in ("document", "docs/", "guidance", "readme")):
        kinds.add("documentation")
    if any(term in text for term in ("migration", "backfill", "rollback", "cursor", "schema")):
        kinds.add("migration")
    if any(term in text for term in ("metric", "logging", "observability", "trace")):
        kinds.add("observability")
    # Consumer/compatibility statements are verified MECHANICALLY by the
    # verification loop's symbol sweep (schema 4); an agent-attached "impact"
    # evidence path would reintroduce self-attestation, so no kind is emitted.
    if any(term in text for term in ("secret", "credential", "authorization", "prompt injection", "untrusted")):
        kinds.add("security")
    return sorted(kinds)


def artifact_hints(statement: str) -> list[str]:
    hints = []
    for token in re.findall(r"`([^`]+)`", statement):
        if "/" in token or re.search(r"\.(?:md|py|json|ya?ml|ts|tsx|js|sql)$", token, re.I):
            hints.append(token)
    return sorted(set(hints))


def candidate_statements(task: str) -> list[tuple[int, str, str]]:
    """Collect explicit bullets plus normative prose while ignoring examples/code."""
    rows: list[tuple[int, str, str]] = []
    in_fence = False
    normative = re.compile(
        r"\b(?:must|shall|required|never|do not|don't|cannot|may not|preserve|implement|"
        r"update|return exactly|raise|reject|keep|track|write|run|move|replace|build|fix)\b",
        re.I,
    )
    for number, raw in enumerate(task.splitlines(), start=1):
        stripped = raw.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not stripped:
            continue
        bullet = re.match(r"^\s*(?:[-*]|\d+[.)])\s+(.+?)\s*$", raw)
        if bullet:
            rows.append((number, bullet.group(1), "list-item"))
            continue
        if stripped.lower().startswith("# task:"):
            rows.append((number, stripped.split(":", 1)[1].strip(), "task-objective"))
            continue
        if stripped.startswith("#"):
            continue
        for sentence in re.split(r"(?<=[.!?])\s+", stripped):
            sentence = sentence.strip()
            if len(sentence) >= 4 and normative.search(sentence):
                rows.append((number, sentence, "normative-prose"))
    deduped = []
    seen = set()
    for row in rows:
        key = normalized(row[1])
        if key not in seen:
            seen.add(key)
            deduped.append(row)
    return deduped


def extract_requirements(task: str) -> list[dict[str, Any]]:
    requirements = []
    for number, statement, source_kind in candidate_statements(task):
        requirements.append({
            "id": requirement_id(statement),
            "statement": statement,
            "source_line": number,
            "source_kind": source_kind,
            "status": "pending",
            "evidence_required": evidence_types(statement),
            "artifact_hints": artifact_hints(statement),
        })
    if not requirements:
        statement = normalized(task)
        requirements.append({
            "id": requirement_id(statement),
            "statement": statement,
            "source_line": 1,
            "source_kind": "whole-task-fallback",
            "status": "pending",
            "evidence_required": ["behavior"],
            "artifact_hints": [],
        })
    return requirements


def find_ambiguities(requirements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ambiguities = []
    for req in requirements:
        text = req["statement"].lower()
        descriptions = []
        if "non-empty string" in text and not any(term in text for term in ("non-blank", "whitespace", "strip")):
            descriptions.append("Non-empty does not define whether whitespace-only strings are valid.")
        if ("must state" in text or "document" in text) and "verbatim" not in text and "exact phrase" not in text:
            descriptions.append("Documentation requirement is semantic; an evaluator must accept equivalent wording and Markdown formatting.")
        for term in ("appropriate", "as needed", "etc.", "and so on"):
            if term in text:
                descriptions.append(f"Subjective scope term requires an authoritative interpretation: {term}")
        for description in descriptions:
            digest = hashlib.sha256((req["id"] + description).encode("utf-8")).hexdigest()[:8].upper()
            ambiguities.append({"id": f"AMB-{digest}", "requirement_id": req["id"], "description": description, "material": True, "status": "unresolved", "resolution": None})
    return ambiguities


def compile_ledger(task: str, source: str = "task.md") -> dict[str, Any]:
    requirements = extract_requirements(task)
    return {
        "schema_version": 2,
        "status": "candidate",
        "source": source,
        "task_sha256": hashlib.sha256(task.encode("utf-8")).hexdigest().upper(),
        "requirements": requirements,
        "coverage": {
            "strategy": "explicit list items, task objective and normative prose outside code fences",
            "captured_statement_count": len(requirements),
            "uncaptured_normative_statement_count": 0
        },
        "ambiguities": find_ambiguities(requirements),
        "completion_rule": "Every applicable requirement must be verified with reproducible evidence; every material ambiguity must be resolved or completion is blocked."
    }


def compact_ledger(ledger: dict[str, Any]) -> dict[str, Any]:
    """Preserve complete objective coverage in a smaller Mode 1 representation."""
    return {
        "schema_version": 2,
        "ledger_profile": "compact",
        "source": ledger["source"],
        "task_sha256": ledger["task_sha256"],
        "requirements": [
            {
                "id": row["id"],
                "statement": row["statement"],
                "source_line": row["source_line"],
                "status": row["status"],
                "evidence_required": row["evidence_required"],
            }
            for row in ledger["requirements"]
        ],
        "ambiguities": [
            {
                "id": row["id"],
                "requirement_id": row["requirement_id"],
                "description": row["description"],
                "material": row["material"],
                "status": row["status"],
            }
            for row in ledger["ambiguities"]
        ],
        "coverage": {
            "captured_statement_count": len(ledger["requirements"]),
            "uncaptured_normative_statement_count": 0,
        },
        "completion_rule": ledger["completion_rule"],
    }


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--task")
    group.add_argument("--task-file", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    task = args.task if args.task is not None else args.task_file.read_text(encoding="utf-8-sig")
    ledger = compile_ledger(task, str(args.task_file or "inline-task"))
    text = json.dumps(ledger, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
