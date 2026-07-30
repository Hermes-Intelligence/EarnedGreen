#!/usr/bin/env python3
"""Tests for the two patterns generalised out of the 2026-07-21 client instrument.

Every test below is written so that it FAILS if the mechanism silently degrades
into the weaker thing it was built to replace. A ledger that accepts a sourceless
fact is a spec instrument with a data label; an extractor that returns an empty
rule set is a checker that passes everything.

    python tests/test_fact_ledger_and_host_rules.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import fact_ledger          # noqa: E402
import host_rules           # noqa: E402

PASS, FAIL = [], []


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASS if condition else FAIL).append(f"{name}{' — ' + detail if detail else ''}")


# ── fact ledger ───────────────────────────────────────────────────────────────
def test_sourceless_fact_is_refused() -> None:
    ledger = fact_ledger.FactLedger()
    try:
        ledger.register("total", lambda: 5, source="")
        check("sourceless fact refused", False, "it was accepted")
    except ValueError as exc:
        check("sourceless fact refused", "rank 2" in str(exc), str(exc)[:60])


def test_mixed_layers_require_labels() -> None:
    ledger = fact_ledger.FactLedger()
    ledger.register("a", lambda: 10, source="q1", layer="collection")
    ledger.register("b", lambda: 20, source="q2", layer="intelligence")
    ledger.register("c", lambda: 30, source="q3")            # no layer
    try:
        ledger.derive_all()
        check("unlabelled fact refused when layers differ", False, "it was accepted")
    except ValueError as exc:
        check("unlabelled fact refused when layers differ", "'c'" in str(exc) or "c" in str(exc))


def test_single_layer_needs_no_labels() -> None:
    ledger = fact_ledger.FactLedger()
    ledger.register("a", lambda: 10, source="q1")
    ledger.register("b", lambda: 20, source="q2")
    ledger.derive_all()
    check("single-layer ledger derives without labels", ledger.summary()["usable"])


def test_empty_derivation_is_a_failure_not_a_zero() -> None:
    ledger = fact_ledger.FactLedger()
    ledger.register("reachable", lambda: 42, source="q1")
    ledger.register("unreachable", lambda: [], source="q2")
    summary = ledger.derive_all()
    check("empty result reported as failure", summary["failed"] == ["unreachable"],
          str(summary["failed"]))
    check("empty result blocks usable", not summary["usable"])


def test_raising_derivation_is_captured_not_propagated() -> None:
    ledger = fact_ledger.FactLedger()

    def boom():
        raise ConnectionError("no route to host")

    ledger.register("db", boom, source="SELECT 1")
    summary = ledger.derive_all()
    check("raising derivation captured", "ConnectionError" in summary["facts"]["db"]["error"])


def test_audit_finds_the_invented_number() -> None:
    ledger = fact_ledger.FactLedger()
    ledger.register("records", lambda: 238_000_000, source="SELECT count(*)")
    ledger.register("platforms", lambda: 6, source="SELECT count(DISTINCT platform)")
    clean = ledger.derive_all() and ledger.audit(
        "6 platforms and 238,000,000 records.")
    check("clean document passes", clean["clean"], str(clean["unledgered"]))

    dirty = ledger.audit("6 platforms, 238,000,000 records, and 41 states.")
    check("invented number caught", dirty["unledgered"] == [41.0], str(dirty["unledgered"]))


def test_audit_sees_numbers_in_awkward_positions() -> None:
    """The first version could not see a number that ended a sentence.

    Its own demo was written to fail and passed for that reason. Every shape below
    is one a real document produces, and each one was invisible or mangled at some
    point while this file was being written.
    """
    ledger = fact_ledger.FactLedger()
    ledger.register("anchor", lambda: 999_999, source="q")
    ledger.derive_all()

    cases = {
        "History runs back to 1963.": 1963.0,          # sentence-final, the demo's bug
        "Coverage reached 1963": 1963.0,               # end of string
        "(1963)": 1963.0,                              # bracketed
        "Growth was 12.5% last year.": 12.5,           # decimal, sentence-final
        "Across 238,000,000 records.": 238000000.0,    # grouped, sentence-final
        "Rows: 1963, and rising.": 1963.0,             # comma-followed
    }
    for text, expected in cases.items():
        found = ledger.audit(text)["unledgered"]
        check(f"sees {expected:g} in {text!r}", found == [expected], f"got {found}")

    # Structure is not a claim: flagging the parts of a date buries real findings.
    quiet = ledger.audit("Reviewed on 2026-07-21 at 14:30, release v0.6.5, 999,999 rows.")
    check("dates, times and versions are not treated as claims",
          quiet["clean"], str(quiet["unledgered"]))


def test_audit_ignores_uninteresting_smalls() -> None:
    ledger = fact_ledger.FactLedger()
    ledger.register("x", lambda: 5000, source="q")
    ledger.derive_all()
    result = ledger.audit("There are 3 tiers and 5000 rows across 2 regions.")
    check("small integers not flagged as invented", result["clean"], str(result["unledgered"]))


def test_audit_reports_derived_but_unused() -> None:
    ledger = fact_ledger.FactLedger()
    ledger.register("used", lambda: 7777, source="q1")
    ledger.register("unused", lambda: 8888, source="q2")
    ledger.derive_all()
    result = ledger.audit("Only 7777 appears here.")
    check("unused fact reported", result["derived_but_unused"] == ["unused"],
          str(result["derived_but_unused"]))


def test_diff_detects_drift() -> None:
    first = fact_ledger.FactLedger()
    first.register("n", lambda: 100, source="q")
    earlier = first.derive_all()

    second = fact_ledger.FactLedger()
    second.register("n", lambda: 101, source="q")
    second.derive_all()
    moved = second.diff(earlier)
    check("drift detected", not moved["stable"] and moved["moved"][0]["now"] == 101)


def test_paginated_count_crosses_pages() -> None:
    pages = {None: ([1, 2, 3], "t1"), "t1": ([4, 5], "t2"), "t2": ([6], None)}
    total = fact_ledger.paginated_count(lambda token: pages[token])
    check("paginated count crosses pages", total == 6, f"got {total}")


# ── host rules ────────────────────────────────────────────────────────────────
def test_js_literal_survives_brace_in_string() -> None:
    source = 'export const BRANDS = [{ key: "a", tagline: "we {win} always" }, { key: "b" }];'
    block = host_rules.js_literal(source, "BRANDS")
    check("balanced reader survives brace inside a string",
          block.count('key:') == 2, block[:70])


def test_js_extractor_finds_palette_and_names(tmp: Path) -> None:
    path = tmp / "brandBook.js"
    path.write_text(
        'export const BRANDS = [{ key: "alpha", name: "Alpha", tagline: "one {two}" }];\n'
        'export const COLORS = [{ name: "Ink", hex: "#101820" }, { name: "Sun", hex: "#F2A900" }];\n',
        encoding="utf-8")
    rules = host_rules.extract(path)
    check("js extractor usable", rules.usable, str(rules.notes))
    check("js extractor found the palette",
          rules.values.get("_palette") == ["#101820", "#F2A900"],
          str(rules.values.get("_palette")))
    check("js extractor found brand scalars", "alpha" in rules.values.get("BRANDS", []))


def test_json_extractor_flattens(tmp: Path) -> None:
    path = tmp / "tokens.json"
    path.write_text(json.dumps({"color": {"bg": "#fff"}, "space": {"sm": 4}}), encoding="utf-8")
    rules = host_rules.extract(path)
    check("json extractor flattens nested tokens",
          rules.values["tokens"]["color.bg"] == "#fff", str(rules.values))


def test_css_extractor_reads_variables(tmp: Path) -> None:
    path = tmp / "theme.css"
    path.write_text(":root { --brand-ink: #101820; --space-1: 4px; }", encoding="utf-8")
    rules = host_rules.extract(path)
    check("css extractor reads variables",
          rules.values["variables"]["--brand-ink"] == "#101820", str(rules.values))


def test_directives_extractor_reads_prose(tmp: Path) -> None:
    path = tmp / "CONVENTIONS.md"
    path.write_text("- Components MUST live under src/components.\n"
                    "- NEVER import from dist.\n"
                    "Ordinary prose with no directive in it.\n", encoding="utf-8")
    rules = host_rules.extract(path)
    check("directives extracted", len(rules.values["directives"]) == 2,
          str(rules.values["directives"]))


def test_empty_extraction_is_unusable_not_empty(tmp: Path) -> None:
    path = tmp / "nothing.css"
    path.write_text("/* a stylesheet with no custom properties at all */", encoding="utf-8")
    rules = host_rules.extract(path)
    check("empty extraction is unusable", not rules.usable)
    check("empty extraction says why",
          any("ZERO rules" in n for n in rules.notes), str(rules.notes))


def test_unknown_format_is_named(tmp: Path) -> None:
    path = tmp / "thing.bin"
    path.write_bytes(b"\x00\x01")
    rules = host_rules.extract(path)
    check("unknown format reported", not rules.usable and "no extractor" in rules.notes[0])


def test_missing_file_is_named(tmp: Path) -> None:
    rules = host_rules.extract(tmp / "absent.json")
    check("missing file reported", not rules.usable and "does not exist" in rules.notes[0])


def test_discover_skips_vendored(parent: Path) -> None:
    # Its own directory: the other tests write host files into the shared tmp, and
    # a discovery assertion that reads their leftovers proves nothing about vendoring.
    tmp = parent / "discovery"
    (tmp / "node_modules" / "pkg").mkdir(parents=True)
    (tmp / "node_modules" / "pkg" / "tokens.json").write_text("{}", encoding="utf-8")
    (tmp / "src").mkdir()
    (tmp / "src" / "tokens.json").write_text('{"a": 1}', encoding="utf-8")
    hits = host_rules.discover(tmp)
    check("discovery skips node_modules",
          len(hits) == 1 and hits[0] == tmp / "src" / "tokens.json", str(hits))


def test_rules_carry_provenance(tmp: Path) -> None:
    path = tmp / "theme.css"
    path.write_text(":root { --a: 1px; }", encoding="utf-8")
    payload = host_rules.extract(path).as_dict()
    check("rules carry host provenance",
          payload["provenance"] == "host" and payload["rank"] == 3)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    test_sourceless_fact_is_refused()
    test_mixed_layers_require_labels()
    test_single_layer_needs_no_labels()
    test_empty_derivation_is_a_failure_not_a_zero()
    test_raising_derivation_is_captured_not_propagated()
    test_audit_finds_the_invented_number()
    test_audit_sees_numbers_in_awkward_positions()
    test_audit_ignores_uninteresting_smalls()
    test_audit_reports_derived_but_unused()
    test_diff_detects_drift()
    test_paginated_count_crosses_pages()
    test_js_literal_survives_brace_in_string()

    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        test_js_extractor_finds_palette_and_names(tmp)
        test_json_extractor_flattens(tmp)
        test_css_extractor_reads_variables(tmp)
        test_directives_extractor_reads_prose(tmp)
        test_empty_extraction_is_unusable_not_empty(tmp)
        test_unknown_format_is_named(tmp)
        test_missing_file_is_named(tmp)
        test_discover_skips_vendored(tmp)
        test_rules_carry_provenance(tmp)

    for line in PASS:
        print(f"  ok    {line}")
    for line in FAIL:
        print(f"  FAIL  {line}")
    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
