#!/usr/bin/env python3
"""Relation predicates for code with NO history — layer 2 of the oracle stack.

Layer 1 (diff_oracle) needs a before/after pair. Most real work has none: the
code is being written NOW, or is broken NOW with no fix in sight. This layer
derives verification from RELATIONS a single implementation either honours or
does not — no answer-oracle, no history, no mind writing predicates:

  determinism   the same input, run twice, must emit the same stream
  co-variation  inputs differing in a field must emit differing streams — the
                mechanical definition of NOT HARDCODED
  sentinel      a unique token planted in the input must reach the emissions —
                no silent data loss
  totality      an input the implementation handles today must not crash

TWO OUTPUTS, BOTH THE POINT:

  findings  relations the CURRENT code violates — suspected defects, surfaced
            with zero oracle knowledge. This is what "the code is broken and
            there is no diff" needs first: somewhere to look.
  pins      relations the current code honours, frozen as forward predicates.
            We never demand more than the code already does — the envelope is
            MEASURED, then pinned — so the out-of-domain over-constraint class
            (which killed 3 of 9 authored checks and 40 of 70 diff candidates)
            is structurally impossible here.

THE VACUITY RULE, ONE LEVEL UP AGAIN: a predicate class that cannot fail is
decoration. `admit_machinery` builds a CONSTRUCTIVE MUTANT per class — a
wrapper that ignores its input (hardcode), drops half its emissions (lossy),
injects noise (nondet) — and the class is trusted only if it reddens on its
mutant while green on the real module. Mechanical, zero judgement, zero calls.

Relations are implementation-agnostic: pins mined from one implementation are
expected to hold on any CORRECT implementation (registered as R-2), unlike
layer-1 pins, which pin the after-state's projected values.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import diff_oracle  # reuses the driver, capture and the projection vocabulary

MODULE_REL = "src/editionPdf.js"
REAL_REL = "src/editionPdf_real_.mjs"

# Sentinels: improbable tokens whose only job is to be findable in emissions.
SENTINELS = {
    "cov-summary-a": "SNTLSUMA9Q", "cov-summary-b": "SNTLSUMB7K",
    "cov-title-a": "SNTLTITA4X", "cov-title-b": "SNTLTITB2V",
    "cov-block-a": "SNTLBLKA6M", "cov-block-b": "SNTLBLKB8W",
    # The URL sentinel is the WHOLE URL: the pin holds only if some single
    # emitted piece contains it unbroken, so any wrapping/splitting/punctuation
    # handling that tears a URL apart reddens the pin. Added because the
    # coverage manifest's first live render caught url-integrity UNCOVERED —
    # diff derives nothing there (before==after on URLs) and no sentinel
    # reached into that dimension. The manifest names a gap; this closes it.
    "url-sentinel": "https://sntl-url-9q3kx.example/path/a_b?x=1&y=2",
}

COVARIATION_PAIRS = [
    ("cov-summary-a", "cov-summary-b", "summary"),
    ("cov-title-a", "cov-title-b", "title"),
    ("cov-block-a", "cov-block-b", "block prose"),
]


def build_relation_corpus() -> dict[str, Any]:
    """Deterministic, sentinel-planted, boundary-including corpus.

    Domain knowledge (the module's public input shape), never answer knowledge:
    nothing here names a convention. Boundary inputs are included so that the
    envelope PINNED covers them — if the code handles an empty summary today,
    sliding back to a crash tomorrow is a caught regression.
    """
    def edition(title: str, summary: str, blocks: list[dict[str, Any]]) -> dict[str, Any]:
        return {"title": title, "output_kind": "report",
                "generated_at": "2026-07-01T09:00:00Z",
                "content_json": {"summary": summary, "blocks": blocks}}

    inputs = [
        {"id": "det-1", "edition": edition("Determinism One", "A stable paragraph about findings.", [])},
        {"id": "det-2", "edition": edition("Determinism Two", "Another paragraph.",
                                           [{"order": 1, "title": "S", "prose": "Body of the section."}])},
        {"id": "cov-summary-a", "edition": edition("Same Title", f"Summary carries {SENTINELS['cov-summary-a']} inside.", [])},
        {"id": "cov-summary-b", "edition": edition("Same Title", f"Summary carries {SENTINELS['cov-summary-b']} inside.", [])},
        {"id": "cov-title-a", "edition": edition(f"Title {SENTINELS['cov-title-a']}", "Fixed summary text.", [])},
        {"id": "cov-title-b", "edition": edition(f"Title {SENTINELS['cov-title-b']}", "Fixed summary text.", [])},
        {"id": "cov-block-a", "edition": edition("Block Cov", "Lead.",
                                                 [{"order": 1, "title": "B", "prose": f"Block holds {SENTINELS['cov-block-a']} here."}])},
        {"id": "cov-block-b", "edition": edition("Block Cov", "Lead.",
                                                 [{"order": 1, "title": "B", "prose": f"Block holds {SENTINELS['cov-block-b']} here."}])},
        {"id": "edge-empty-summary", "edition": edition("Edge Empty", "", [])},
        {"id": "edge-no-blocks", "edition": edition("Edge NoBlocks", "Only a summary, no blocks at all.", [])},
        {"id": "edge-long", "edition": edition("Edge Long", " ".join(f"Chunk {k} of a very long body." for k in range(400)), [])},
        {"id": "edge-unicode", "edition": edition("Edge Unicode", "Zażółć — „quotes”, café, naïve, – dashes.", [])},
        {"id": "url-sentinel", "edition": edition(
            "URL Integrity",
            f"Full detail at {SENTINELS['url-sentinel']} for the record.", [])},
    ]
    return {"schema_version": 1, "inputs": inputs}


# --- mining -----------------------------------------------------------------------

def mine(workspace: Path, corpus_file: Path) -> dict[str, Any]:
    """Run the relations against ONE implementation: violations become findings,
    honoured relations become pins."""
    first = diff_oracle.capture(workspace, corpus_file)
    second = diff_oracle.capture(workspace, corpus_file)  # determinism needs two runs
    findings: list[dict[str, Any]] = []
    pins: list[dict[str, Any]] = []

    for input_id in sorted(first):
        stream = first[input_id]
        if isinstance(stream, dict):  # driver reported a crash
            findings.append({"kind": "totality", "input_id": input_id,
                             "suspicion": f"crashes on an input of its public shape: {stream.get('__error__', '')[:200]}"})
            continue
        pins.append({"id": f"total::{input_id}", "kind": "totality", "input_id": input_id})
        if second.get(input_id) != stream:
            findings.append({"kind": "determinism", "input_id": input_id,
                             "suspicion": "two runs on the identical input emitted different streams"})
        else:
            pins.append({"id": f"det::{input_id}", "kind": "determinism", "input_id": input_id})

    for a, b, field in COVARIATION_PAIRS:
        sa, sb = first.get(a), first.get(b)
        if not isinstance(sa, list) or not isinstance(sb, list):
            continue  # already a totality finding
        if sa == sb:
            findings.append({"kind": "co-variation", "input_id": f"{a}|{b}",
                             "suspicion": f"inputs differing in {field} emitted IDENTICAL streams: "
                                          "the output does not depend on that field (hardcode suspect)"})
        else:
            pins.append({"id": f"cov::{a}|{b}", "kind": "co-variation", "inputs": [a, b], "field": field})

    for input_id, token in SENTINELS.items():
        stream = first.get(input_id)
        if not isinstance(stream, list):
            continue
        if any(token in piece for piece in stream):
            pins.append({"id": f"sentinel::{input_id}", "kind": "sentinel",
                         "input_id": input_id, "token": token})
        else:
            findings.append({"kind": "sentinel", "input_id": input_id,
                             "suspicion": f"the planted token {token} never reached the emissions: "
                                          "content in this field is silently lost"})
    return {"schema_version": 1, "findings": findings, "pins": pins,
            "rule": ("violations now are FINDINGS (somewhere to look, no oracle needed); honoured "
                     "relations are PINNED forward (the measured envelope must not slide back)")}


def evaluate(pins: list[dict[str, Any]], workspace: Path, corpus_file: Path) -> dict[str, Any]:
    """Do this implementation's emissions honour the pinned relations?"""
    first = diff_oracle.capture(workspace, corpus_file)
    second = diff_oracle.capture(workspace, corpus_file)
    rows = []
    for pin in pins:
        kind = pin["kind"]
        if kind == "totality":
            ok = isinstance(first.get(pin["input_id"]), list)
        elif kind == "determinism":
            stream = first.get(pin["input_id"])
            ok = isinstance(stream, list) and second.get(pin["input_id"]) == stream
        elif kind == "co-variation":
            a, b = pin["inputs"]
            sa, sb = first.get(a), first.get(b)
            ok = isinstance(sa, list) and isinstance(sb, list) and sa != sb
        elif kind == "sentinel":
            stream = first.get(pin["input_id"])
            ok = isinstance(stream, list) and any(pin["token"] in piece for piece in stream)
        else:
            ok = False
        rows.append({"id": pin["id"], "verdict": "GREEN" if ok else "RED"})
    red = [row["id"] for row in rows if row["verdict"] == "RED"]
    return {"green": not red, "red_pin_ids": red, "checks": rows}


# --- constructive mutants (the vacuity rule for predicate classes) ----------------

_WRAPPER_HEADER = f'import {{ buildEditionDoc as real }} from "./{Path(REAL_REL).name}"\n'

_MUTANTS = {
    # Ignores its input: the mechanical essence of hardcoding.
    "hardcode": _WRAPPER_HEADER + """
const FIXED = { title: "Fixed", output_kind: "report",
  content_json: { summary: "The same summary every time.", blocks: [] } }
export async function buildEditionDoc(_edition, meta) { return real(FIXED, meta || {}) }
""",
    # Emits, then silently drops the second half of what it emitted.
    "lossy": _WRAPPER_HEADER + """
export async function buildEditionDoc(edition, meta) {
  const out = await real(edition, meta || {})
  const record = globalThis.__JSPDF_RECORD__
  if (record && record.text.length > 1) record.text.length = Math.ceil(record.text.length / 2)
  return out
}
""",
    # Injects noise: two identical calls never emit the same stream.
    "nondet": _WRAPPER_HEADER + """
let counter = 0
export async function buildEditionDoc(edition, meta) {
  const out = await real(edition, meta || {})
  const record = globalThis.__JSPDF_RECORD__
  if (record) record.text.push({ s: "noise-" + (counter++) + "-" + Math.random(), x: 0, y: 0, page: 1 })
  return out
}
""",
}

# Which pin kinds MUST redden on which mutant for the class to be non-vacuous.
EXPECTED_CATCHES = {
    "hardcode": {"co-variation", "sentinel"},
    "lossy": {"sentinel"},
    "nondet": {"determinism"},
}


def make_mutant(workspace: Path, kind: str, destination: Path) -> Path:
    if kind not in _MUTANTS:
        raise ValueError(f"unknown mutant kind {kind!r}")
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(workspace, destination)
    real_module = destination / MODULE_REL
    real_module.rename(destination / REAL_REL)
    (destination / MODULE_REL).write_text(_MUTANTS[kind], encoding="utf-8")
    return destination


def admit_machinery(workspace: Path, corpus_file: Path, scratch: Path) -> dict[str, Any]:
    """Prove every predicate class CAN fail: red on its constructive mutant,
    green on the real module. A class that fails this is decoration and the
    caller must not trust its pins."""
    mined = mine(workspace, corpus_file)
    real_eval = evaluate(mined["pins"], workspace, corpus_file)
    rows = []
    for kind, expected in EXPECTED_CATCHES.items():
        mutant = make_mutant(workspace, kind, scratch / f"mutant-{kind}")
        outcome = evaluate(mined["pins"], mutant, corpus_file)
        caught_kinds = {pin_id.split("::")[0] for pin_id in outcome["red_pin_ids"]}
        translate = {"cov": "co-variation", "det": "determinism",
                     "sentinel": "sentinel", "total": "totality"}
        caught = {translate[k] for k in caught_kinds}
        rows.append({"mutant": kind, "expected_catch_by": sorted(expected),
                     "caught_by": sorted(caught),
                     "verdict": "PASS" if expected <= caught else "FAIL"})
    verdict = ("PASS" if real_eval["green"] and all(row["verdict"] == "PASS" for row in rows)
               else "FAIL")
    return {"schema_version": 1, "verdict": verdict,
            "green_on_real_module": real_eval["green"],
            "red_on_real_module": real_eval["red_pin_ids"],
            "classes": rows, "pins": len(mined["pins"]), "findings": mined["findings"]}


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description="Mine relation predicates from one implementation (zero calls).")
    sub = parser.add_subparsers(dest="action", required=True)
    mine_p = sub.add_parser("mine", help="findings + forward pins from one workspace")
    mine_p.add_argument("--workspace", type=Path, required=True)
    mine_p.add_argument("--output", type=Path, required=True)
    admit_p = sub.add_parser("admit", help="prove every predicate class can fail (constructive mutants)")
    admit_p.add_argument("--workspace", type=Path, required=True)
    admit_p.add_argument("--scratch", type=Path, required=True)
    admit_p.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    corpus_file = args.output.parent / "relation-corpus.json"
    corpus_file.write_text(json.dumps(build_relation_corpus(), ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    if args.action == "mine":
        result = mine(args.workspace, corpus_file)
    else:
        result = admit_machinery(args.workspace, corpus_file, args.scratch)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "pins" or isinstance(value, int)},
                     ensure_ascii=False, indent=2)[:2000])


if __name__ == "__main__":
    main()
