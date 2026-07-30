#!/usr/bin/env python3
"""The coverage manifest: what green MEANS — and, louder, what it does NOT.

Every silent defect this programme ever measured lived in the same place: a
dimension nobody's check covered, while the overall verdict said PASS. The
uncovered dimension was never NAMED, so green quietly claimed it. This module
ends that: a gate stops emitting a bare verdict and starts emitting a typed one—

  EARNED GREEN on: <dimensions, each backed by >=1 admitted check, with the
                    check's provenance: diff-derived | relation | authored | repo-tests>
  UNVERIFIED:      <dimensions with NO admitted check — named, with the reason,
                    so nobody can read green as covering them>

An uncovered dimension you NAMED is a known gap awaiting a human decision.
An uncovered dimension you never listed is a silent defect waiting to ship.
The difference between those two sentences is this file.

Dimensions come from the repo (a conventions/requirements list — one per
documented rule), plus the STRUCTURAL dimensions the oracle stack itself owns
(regression envelope, determinism, co-variation, data preservation, totality).
No model calls; no judgement; pure bookkeeping made unskippable.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

VALID_PROVENANCE = {"diff-derived", "relation", "authored", "repo-tests",
                    # oracle-bootstrap sources (tiered-loop package): each names
                    # WHERE a green came from when there was no answer key
                    "spec", "council", "acceptance", "finding",
                    # re-derived from the SYSTEM'S OWN DATA (a number in a document
                    # recomputed from the database it claims to describe). The agent
                    # cannot author this one into being true.
                    "data",
                    # extracted MECHANICALLY from the host codebase (design tokens,
                    # sizing tables, the idioms sibling surfaces already use). The
                    # answer was in the repo; the agent only had to look.
                    "host",
                    # a strong model READ this dimension and did not object. That
                    # is not verification: judges report 0.72-0.94 pass where true
                    # accuracy is 0.20, and ensembling them does not fix it. This
                    # provenance exists so such dimensions can never be counted as
                    # earned green — see NON_CERTIFYING_PROVENANCE below.
                    "reviewed-unverified"}

# Provenances that unblock PROCESS but never certify CORRECTNESS. A dimension
# covered only by these stays in the manifest's named-unverified column.
NON_CERTIFYING_PROVENANCE = {"reviewed-unverified"}

# ── How far a check's source sits FROM THE AGENT ──────────────────────────────
# The ordering is measured, not assumed. Across this programme:
#   diff-derived predicates + a forcing loop  -> positive on two hard families
#                                                (88.7 vs 33.3, 71.3 vs 43.0)
#   agent-authored, gate-admitted checks      -> ZERO lift over configured vanilla
#                                                (9 runs, all 92, same defect rate)
#   spec-derived predicates                   -> SATURATED on family-4: both arms
#                                                near-perfect while the owner's eye
#                                                found four defects none of them saw
# Everything the agent authors about its own correctness has measured zero.
# Everything that comes from outside the agent has carried the wins. So the rank
# is "distance from the agent", and it is what `independence` below counts.
PROVENANCE_RANK = {
    "diff-derived": 4,          # real commits: what a human actually changed
    "data": 4,                  # recomputed from the system's own data
    "repo-tests": 4,            # the repo's suite, written before this task existed
    "host": 3,                  # extracted mechanically from the host codebase
    "relation": 3,              # structural relations captured at birth
    "acceptance": 3,            # frozen on a human's explicit acceptance
    "finding": 3,               # a defect that was actually observed
    "spec": 2,                  # the agent's rendering of prose — saturates
    "council": 1,               # another model's opinion
    "authored": 1,              # the agent's own idea of what should hold
    "reviewed-unverified": 0,   # a model read it; that is not a check
}

# A check is INDEPENDENT when its content could not have been invented by the
# agent doing the work. Note where the line falls: `spec` is BELOW it. A spec is
# usually written by a person, but the predicate is still the agent's rendering
# of that prose — which is exactly the rung that saturated on family-4, where a
# fully spec-derived instrument scored two builds near-identically and missed
# every defect the owner then found by eye.
INDEPENDENCE_FLOOR = 3
INDEPENDENT_PROVENANCE = {name for name, rank in PROVENANCE_RANK.items()
                          if rank >= INDEPENDENCE_FLOOR}


def independence(checks: list[dict[str, Any]]) -> dict[str, Any]:
    """What share of the admitted checks came from a source the agent did not author.

    Reported at task START, not at the end: it predicts whether the eventual green
    will mean anything far better than the verdict itself does. Family-4 would have
    opened at 0% — every predicate spec-derived — and its green was worth exactly
    what that number says.
    """
    certifying = [c for c in checks
                  if c.get("provenance") not in NON_CERTIFYING_PROVENANCE]
    total = len(certifying)
    independent = [c for c in certifying
                   if c.get("provenance") in INDEPENDENT_PROVENANCE]
    by_source: dict[str, int] = {}
    for check in certifying:
        by_source[check.get("provenance", "?")] = by_source.get(check.get("provenance", "?"), 0) + 1
    return {
        "score": round(len(independent) / total, 3) if total else 0.0,
        "independent_checks": len(independent),
        "certifying_checks": total,
        "by_provenance": dict(sorted(by_source.items(),
                                     key=lambda kv: (-PROVENANCE_RANK.get(kv[0], 0), kv[0]))),
        "strongest_source": max((c.get("provenance") for c in certifying),
                                key=lambda p: PROVENANCE_RANK.get(p, 0), default=None),
        "rule": ("independence counts checks whose CONTENT the agent could not have invented; "
                 "spec-derived checks are deliberately excluded — that rung saturated"),
    }


def build(dimensions: list[dict[str, Any]], checks: list[dict[str, Any]]) -> dict[str, Any]:
    """dimensions: [{id, statement?}]; checks: [{id, covers: [dimension ids], provenance}]."""
    declared_ids = [row["id"] for row in dimensions]
    duplicates = sorted({d for d in declared_ids if declared_ids.count(d) > 1})
    if duplicates:
        # two dimensions sharing an id silently become one, and one of them
        # would then be "covered" by the other's check — a bookkeeping bug that
        # manufactures coverage, so it fails loudly
        raise ValueError(f"duplicate dimension ids: {duplicates}")
    known = set(declared_ids)
    coverage: dict[str, list[dict[str, str]]] = {dim: [] for dim in known}
    dangling: list[dict[str, Any]] = []
    for check in checks:
        if not check.get("id"):
            raise ValueError(f"check without an id: {check!r:.120}")
        provenance = check.get("provenance")
        if provenance not in VALID_PROVENANCE:
            raise ValueError(f"check {check.get('id')!r} has provenance {provenance!r}; "
                             f"expected one of {sorted(VALID_PROVENANCE)}")
        for dim in check.get("covers", []):
            if dim not in known:
                # A check claiming an unknown dimension is a bookkeeping bug —
                # surfaced, never silently absorbed into a fake dimension.
                dangling.append({"check": check["id"], "claims": dim})
                continue
            coverage[dim].append({"check": check["id"], "provenance": provenance})

    def certifying(rows: list[dict[str, str]]) -> list[dict[str, str]]:
        return [r for r in rows if r["provenance"] not in NON_CERTIFYING_PROVENANCE]

    verified = [{"id": dim, "checks": rows} for dim, rows in coverage.items()
                if certifying(rows)]
    # A dimension whose ONLY coverage is a strong-model review is NOT verified:
    # it is reviewed. It stays in the unverified column, carrying the fact that
    # a reviewer looked — so nobody mistakes reading for checking.
    unverified = []
    for row in dimensions:
        rows = coverage[row["id"]]
        if certifying(rows):
            continue
        entry = {"id": row["id"], "statement": row.get("statement", "")}
        if rows:
            entry["reviewed_by"] = [r["check"] for r in rows]
            entry["note"] = ("a strong model reviewed this and did not object; that is not "
                             "verification — a person accepts it or a predicate covers it")
        unverified.append(entry)
    return {
        "schema_version": 2,
        "verified": sorted(verified, key=lambda row: row["id"]),
        "unverified": sorted(unverified, key=lambda row: row["id"]),
        "dangling_claims": dangling,
        "independence": independence(checks),
        "rule": ("green speaks ONLY for the verified list; every unverified dimension is named so "
                 "nobody can read green as covering it, and a model's review never moves a "
                 "dimension into the verified list"),
    }


def render(manifest: dict[str, Any]) -> str:
    """The report opens with what is NOT covered.

    This ordering is the whole point and it was earned the hard way. On family-4 a
    viewport-overflow predicate was written, was correctly rejected as vacuous, and
    its dimension correctly landed in the unverified column — the machinery worked
    perfectly. Nobody read it, because the summary opened with green. The owner then
    found that exact defect by eye within a minute of opening the build.

    A reader gives the first line their full attention and the last line almost
    none. So the first line is the gap.
    """
    unverified = manifest["unverified"]
    lines: list[str] = []

    if unverified:
        lines.append(f"NOT MECHANICALLY COVERED — {len(unverified)} behaviour(s) you asked for:")
        for row in unverified:
            statement = f" - {row['statement']}" if row.get("statement") else ""
            lines.append(f"  {row['id']}{statement}")
            if row.get("reviewed_by"):
                lines.append(f"      reviewed (NOT verified) by: {', '.join(row['reviewed_by'])}")
        lines.append("  ^ green below says NOTHING about these. Look here first.")
    else:
        lines.append("NOT MECHANICALLY COVERED: none — every declared dimension carries an admitted check.")

    independent = manifest.get("independence")
    if independent:
        pct = round(independent["score"] * 100)
        lines.append("")
        lines.append(f"ORACLE INDEPENDENCE: {pct}%  "
                     f"({independent['independent_checks']}/{independent['certifying_checks']} "
                     f"checks come from a source the agent did not author)")
        if independent["by_provenance"]:
            sources = ", ".join(f"{name}x{count}" for name, count in independent["by_provenance"].items())
            lines.append(f"  sources, strongest first: {sources}")
        if pct == 0 and independent["certifying_checks"]:
            lines.append("  ^ every check is the agent's own rendering of the task. A green here "
                         "means the work agrees with itself.")

    lines.append("")
    lines.append("EARNED GREEN on:")
    for row in manifest["verified"]:
        sources = sorted({entry["provenance"] for entry in row["checks"]})
        lines.append(f"  {row['id']}  ({len(row['checks'])} check(s); {', '.join(sources)})")
    if not manifest["verified"]:
        lines.append("  (nothing: no dimension is backed by an admitted check)")

    if manifest["dangling_claims"]:
        lines.append("")
        lines.append("BOOKKEEPING DEFECTS (checks claiming undeclared dimensions):")
        for row in manifest["dangling_claims"]:
            lines.append(f"  {row['check']} claims {row['claims']!r}")
    return "\n".join(lines)


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description="Typed 'done': verified vs NAMED-unverified dimensions.")
    parser.add_argument("--dimensions", type=Path, required=True, help="JSON: {dimensions:[{id,statement}]}")
    parser.add_argument("--checks", type=Path, required=True, help="JSON: {checks:[{id,covers,provenance}]}")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    dimensions = json.loads(args.dimensions.read_text(encoding="utf-8-sig"))["dimensions"]
    checks = json.loads(args.checks.read_text(encoding="utf-8-sig"))["checks"]
    manifest = build(dimensions, checks)
    if args.output:
        args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(render(manifest))
    raise SystemExit(0 if not manifest["dangling_claims"] else 1)


if __name__ == "__main__":
    main()
