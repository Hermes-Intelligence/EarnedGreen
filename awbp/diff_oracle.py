#!/usr/bin/env python3
"""Derive check predicates MECHANICALLY from the behaviour diff of git history.

WHY THIS EXISTS — the measured trail that leads here:

  * Three interventions asked a MIND to derive predicates from prose, and every
    one produced predicates weaker than the rule, each in a different way:
    iteration (P1 falsified: geometry instead of text), admission (weak
    predicates admit fine — vacuity is not weakness), notes-as-code (style
    transferred, strength did not: non-gluing instead of separation).
  * The only oracles that ever discriminated — every held-out grader in every
    campaign — were derived from the DIFF: what the shipped fix observably
    changed. But they were derived BY HAND, by an expert, over a week.

This module automates that derivation, with zero model calls:

  1. Run the BEFORE and AFTER states on the same deterministic input corpus,
     capturing what each EMITTED (the observable the graders always used).
  2. Compare the two streams under a small library of GENERIC projections
     (sequence, multiset, adjacency bigrams, joined text, charset, count).
     A projection that differs between before and after captures a slice of
     the intended behaviour change — mechanically, no comprehension involved.
  3. Admit a candidate predicate only if it is red-on-before, green-on-after
     AND GREEN ON EVERY OTHER VALID VARIANT (altformat: the committed
     different-but-correct solution). History hands us what task-time admission
     never has — a second valid implementation — so format-pinning predicates
     (the out-of-domain / over-constraint failure class) are killed
     mechanically, not by judgement.

The derived predicate is deliberately humble: "under projection P, on corpus
input I, the output equals the after-state's value". It does not understand
the rule; it pins the OBSERVABLE CONSEQUENCE of the rule being implemented,
which is exactly what a regression oracle is. Whether these humble predicates
beat mind-derived ones on the material minds failed on is a REGISTERED
measurement (evidence/diff-oracle-predictions.json), not an assumption.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
DRIVER = HERE / "diff_oracle_driver.mjs"

NODE_TIMEOUT = 120


# --- generic projections over an emitted stream (list of strings) -----------------

def _seq(stream: list[str]) -> Any:
    return list(stream)


def _multiset(stream: list[str]) -> Any:
    return sorted(stream)


def _uniq(stream: list[str]) -> Any:
    return sorted(set(stream))


def _bigrams(stream: list[str]) -> Any:
    return sorted({f"{a}␟{b}" for a, b in zip(stream, stream[1:])})


def _joined(stream: list[str]) -> Any:
    return " ".join(stream)


def _count(stream: list[str]) -> Any:
    return len(stream)


def _charset(stream: list[str]) -> Any:
    return sorted(set("".join(stream)))


def _kindset(stream: list[str]) -> Any:
    """The SET of event kinds (prefix before the first ':').

    The coarsest useful abstraction of a structured event stream: it answers
    "what KINDS of things did the code do" while ignoring coordinates, counts
    and order — all of which are implementation choices a different-but-valid
    solution is free to make. Added for the era fixture, where pinning draw-event
    sequences would fail every honest reimplementation of a chart (the measured
    over-constraint class, one level up)."""
    return sorted({piece.split(":", 1)[0] for piece in stream})


def _textseq(stream: list[str]) -> Any:
    """Only the emitted TEXT events, in order, content included.

    The complement of kindset: exact on what the code SAID, blind to how it
    DREW. Text content is the convention surface for citation/enum/section
    rules, while draw coordinates are implementation choices — so text families
    and preservation guards pin this, never the full event stream."""
    return [piece for piece in stream if piece.startswith("text:")]


PROJECTIONS: dict[str, Callable[[list[str]], Any]] = {
    "seq": _seq,
    "multiset": _multiset,
    "uniq": _uniq,
    "bigrams": _bigrams,
    "joined": _joined,
    "count": _count,
    "charset": _charset,
    "kindset": _kindset,
    "textseq": _textseq,
}


# --- corpus -----------------------------------------------------------------------

def build_corpus() -> dict[str, Any]:
    """A deterministic corpus of generic agent-prose shapes.

    DOMAIN knowledge, never ANSWER knowledge: the primitives below are markdown
    features of the module's public input shape (links, runs of links with and
    without repetition, list markers, unicode text, long prose, bare URLs) —
    no primitive encodes any convention. Combinatorial repetition (1..6 links,
    duplicate patterns) is a generator dimension, not a hint: repetition is what
    generators do. Seeded by construction: this function is pure.
    """
    url = lambda k: f"https://src{k}.example/ref/{k}"
    link = lambda label, k: f"[{label}]({url(k)})"

    inputs: list[dict[str, Any]] = []

    def add(input_id: str, summary: str, blocks: list[dict[str, Any]] | None = None) -> None:
        inputs.append({
            "id": input_id,
            "edition": {
                "title": f"Corpus {input_id}",
                "output_kind": "report",
                "generated_at": "2026-07-01T09:00:00Z",
                "content_json": {"summary": summary, "blocks": blocks or []},
            },
        })

    # runs of adjacent links: length 1..6, unique labels
    for n in range(1, 7):
        run = "".join(link(str(k + 1), k + 1) for k in range(n))
        add(f"run-unique-{n}", f"Finding stands {run} in the record.")
    # runs with duplication patterns
    for name, labels in [("dup-pair", ["1", "1"]), ("dup-heavy", ["2", "2", "2", "3"]),
                         ("dup-mixed", ["1", "2", "1", "3", "2"]),
                         ("dup-all", ["4", "4", "4", "4"])]:
        run = "".join(link(label, label) for label in labels)
        add(f"run-{name}", f"Observed {run} across sources.")
    # links separated by prose (not a run)
    add("links-spread", f"First {link('1', 1)} then later {link('2', 2)} in text.")
    # list markers in the three common styles
    add("list-dot", "Key points:\n1. First item stands.\n2. Second item follows.\n3. Third closes.")
    add("list-paren", "Steps:\n1) Alpha step.\n2) Beta step.")
    add("list-parens", "Cases:\n(1) One case.\n(2) Another case.\n(3) Final case.")
    # unicode-rich prose
    add("unicode", "Zażółć gęślą jaźń — „curly” quotes, café, naïve, em—dash and – en dash.")
    # a long unbroken paragraph
    add("long-prose", " ".join(f"Sentence number {k} carries weight." for k in range(1, 40)))
    # bare URLs in prose
    add("bare-url", "See https://example.org/a/very/long/path?with=query&and=more for detail.")
    # links inside blocks (the other rendering surface of the public shape)
    add("block-run", "Lead paragraph.",
        blocks=[{"order": 1, "title": "Sect",
                 "prose": f"Body cites {''.join(link(str(k), k) for k in (5, 5, 6, 7, 8))} here."}])
    add("block-list", "Intro.",
        blocks=[{"order": 1, "title": "Steps", "prose": "1. Do this.\n2. Then that."}])
    # plain control
    add("plain", "A plain paragraph with nothing special at all.")

    return {"schema_version": 1, "inputs": inputs}


# --- capture ----------------------------------------------------------------------

def capture(workspace: Path, corpus_file: Path, module_rel: str = "src/editionPdf.js") -> dict[str, Any]:
    completed = subprocess.run(
        ["node", str(DRIVER), str(corpus_file), module_rel],
        cwd=workspace, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=NODE_TIMEOUT)
    if completed.returncode != 0:
        raise RuntimeError(f"driver failed in {workspace}: {completed.stderr[-500:]}")
    return json.loads(completed.stdout)


# --- derivation -------------------------------------------------------------------

def derive(before: dict[str, Any], after: dict[str, Any],
           valid_variants: list[dict[str, Any]]) -> dict[str, Any]:
    """Candidate predicates from every (input, projection) where before != after,
    admitted only when every OTHER valid implementation agrees with after.

    A predicate a valid variant disagrees with is pinning the implementation,
    not the behaviour — the mechanical form of the out-of-domain-inputs /
    over-constraint failure class, and it dies here without any judgement.
    """
    admitted: list[dict[str, Any]] = []
    rejected_format_pinning = 0
    errors: list[str] = []
    for input_id in sorted(before):
        b_stream, a_stream = before.get(input_id), after.get(input_id)
        if not isinstance(b_stream, list) or not isinstance(a_stream, list):
            errors.append(f"{input_id}: driver error before={b_stream!r:.80} after={a_stream!r:.80}")
            continue
        for name, projection in PROJECTIONS.items():
            b_val, a_val = projection(b_stream), projection(a_stream)
            if b_val == a_val:
                continue  # this projection sees no behaviour change on this input
            variant_ok = True
            for variant in valid_variants:
                v_stream = variant.get(input_id)
                if not isinstance(v_stream, list) or projection(v_stream) != a_val:
                    variant_ok = False
                    break
            if not variant_ok:
                rejected_format_pinning += 1
                continue
            expected = json.dumps(a_val, ensure_ascii=False, sort_keys=True)
            admitted.append({
                "id": f"{input_id}::{name}",
                "input_id": input_id,
                "projection": name,
                "expected": a_val,
                "expected_sha256": hashlib.sha256(expected.encode("utf-8")).hexdigest().upper(),
            })
    return {
        "schema_version": 1,
        "admitted": admitted,
        "rejected_format_pinning": rejected_format_pinning,
        "driver_errors": errors,
        "rule": ("a predicate is admitted only if it distinguishes before from after AND every other "
                 "valid implementation agrees with after under it; disagreement means the predicate "
                 "pins an implementation, not the behaviour"),
    }


# --- gen-4: relational predicates ------------------------------------------------
#
# The era fixture measured WHY exact-equality predicates from a single reference
# fail on wide tasks: they pin the reference's rendering choices wholesale
# (era-instrument-analysis-interpretation.json). The abstraction ladder located
# the valid mid-levels, and these two relational forms are exactly those levels:
#
#   kinds-superset    every event KIND the reference GAINED over before must be
#                     present in the solution (subset requirement, never set
#                     equality) — mechanical, single-reference-sufficient, and
#                     it rewards partial real work instead of zeroing it
#   count-direction   per event kind, the solution's count must move in the
#                     SAME DIRECTION relative to before as the reference did
#                     (became-nonzero / became-zero / increased / decreased) —
#                     the v1 `count` clean-win pattern generalized per kind
#
# Red-on-before is STRUCTURAL for both: the gained kinds are disjoint from
# before's kinds by construction, and before sits exactly at the count baseline.
# The altformat/valid-variant filter still applies on top.

def _stream_kinds(stream: list[str]) -> set[str]:
    return {piece.split(":", 1)[0] for piece in stream}


def _stream_kind_counts(stream: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for piece in stream:
        kind = piece.split(":", 1)[0]
        counts[kind] = counts.get(kind, 0) + 1
    return counts


def _direction(baseline: int, after_n: int) -> str | None:
    if baseline == after_n:
        return None
    if baseline == 0:
        return "became-nonzero"
    if after_n == 0:
        return "became-zero"
    return "increased" if after_n > baseline else "decreased"


def _direction_holds(direction: str, baseline: int, n: int) -> bool:
    if direction == "became-nonzero":
        return n > 0
    if direction == "became-zero":
        return n == 0
    if direction == "increased":
        return n > baseline
    if direction == "decreased":
        return n < baseline
    raise ValueError(f"unknown direction {direction!r}")


def derive_relational(before: dict[str, Any], after: dict[str, Any],
                      valid_variants: list[dict[str, Any]]) -> dict[str, Any]:
    """Gen-4 derivation: relational predicates from the same behaviour diff.

    Same admission rule as `derive` — red-on-before (structural here) plus
    agreement of every other valid implementation — but the admitted predicate
    states a RELATION to before, not equality with after."""
    admitted: list[dict[str, Any]] = []
    rejected_by_variant = 0
    errors: list[str] = []
    for input_id in sorted(before):
        b_stream, a_stream = before.get(input_id), after.get(input_id)
        if not isinstance(b_stream, list) or not isinstance(a_stream, list):
            errors.append(f"{input_id}: driver error before={b_stream!r:.80} after={a_stream!r:.80}")
            continue
        variant_streams = []
        variants_ok = True
        for variant in valid_variants:
            v_stream = variant.get(input_id)
            if not isinstance(v_stream, list):
                variants_ok = False
                break
            variant_streams.append(v_stream)
        if not variants_ok:
            errors.append(f"{input_id}: driver error in a valid variant")
            continue

        gains = sorted(_stream_kinds(a_stream) - _stream_kinds(b_stream))
        if gains:
            if all(set(gains) <= _stream_kinds(v) for v in variant_streams):
                admitted.append({
                    "id": f"{input_id}::kinds-gained",
                    "input_id": input_id,
                    "relation": "kinds-superset",
                    "expected": gains,
                })
            else:
                rejected_by_variant += 1

        b_counts, a_counts = _stream_kind_counts(b_stream), _stream_kind_counts(a_stream)
        for kind in sorted(set(b_counts) | set(a_counts)):
            baseline, after_n = b_counts.get(kind, 0), a_counts.get(kind, 0)
            direction = _direction(baseline, after_n)
            if direction is None:
                continue
            if all(_direction_holds(direction, baseline,
                                    _stream_kind_counts(v).get(kind, 0))
                   for v in variant_streams):
                admitted.append({
                    "id": f"{input_id}::count-{kind}-{direction}",
                    "input_id": input_id,
                    "relation": "count-direction",
                    "kind": kind,
                    "baseline": baseline,
                    "direction": direction,
                })
            else:
                rejected_by_variant += 1
    return {
        "schema_version": 1,
        "admitted": admitted,
        "rejected_by_variant": rejected_by_variant,
        "driver_errors": errors,
        "rule": ("relational form of the admission rule: the relation separates before from after "
                 "structurally, and every other valid implementation satisfies it; a relation a valid "
                 "variant violates is still pinning implementation, and dies here"),
    }


def evaluate(predicates: list[dict[str, Any]], streams: dict[str, Any]) -> dict[str, Any]:
    """Run the derived predicates against one implementation's captured streams.

    Handles both exact predicates (no `relation` key / `relation: "equal"`) and
    gen-4 relational predicates — frozen pin files from either generation
    evaluate unchanged."""
    rows = []
    for predicate in predicates:
        stream = streams.get(predicate["input_id"])
        if not isinstance(stream, list):
            rows.append({"id": predicate["id"], "verdict": "ERROR",
                         "reason": f"driver error: {stream!r:.120}"})
            continue
        relation = predicate.get("relation", "equal")
        if relation == "equal":
            actual = PROJECTIONS[predicate["projection"]](stream)
            green = actual == predicate["expected"]
        elif relation == "kinds-superset":
            green = set(predicate["expected"]) <= _stream_kinds(stream)
        elif relation == "count-direction":
            n = _stream_kind_counts(stream).get(predicate["kind"], 0)
            green = _direction_holds(predicate["direction"], predicate["baseline"], n)
        else:
            rows.append({"id": predicate["id"], "verdict": "ERROR",
                         "reason": f"unknown relation {relation!r}"})
            continue
        rows.append({"id": predicate["id"],
                     "verdict": "GREEN" if green else "RED"})
    red = [row["id"] for row in rows if row["verdict"] == "RED"]
    return {"green": not red and all(row["verdict"] == "GREEN" for row in rows),
            "red_predicate_ids": red,
            "errors": [row for row in rows if row["verdict"] == "ERROR"],
            "checks": rows}


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description="Derive predicates from a behaviour diff (zero provider calls).")
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--valid-variant", type=Path, action="append", default=[],
                        help="additional KNOWN-VALID implementations (over-constraint filter)")
    parser.add_argument("--corpus", type=Path, help="corpus JSON; default: the built-in generator")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    corpus_file = args.corpus
    if corpus_file is None:
        corpus_file = args.output.parent / "diff-oracle-corpus.json"
        corpus_file.write_text(json.dumps(build_corpus(), ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
    before = capture(args.before, corpus_file)
    after = capture(args.after, corpus_file)
    variants = [capture(path, corpus_file) for path in args.valid_variant]
    result = derive(before, after, variants)
    result["corpus"] = str(corpus_file)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"admitted": len(result["admitted"]),
                      "rejected_format_pinning": result["rejected_format_pinning"],
                      "driver_errors": len(result["driver_errors"])}, indent=2))


if __name__ == "__main__":
    main()
