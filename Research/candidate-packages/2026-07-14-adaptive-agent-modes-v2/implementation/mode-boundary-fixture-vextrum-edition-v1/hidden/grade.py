#!/usr/bin/env python
"""Hidden grader (vextrum-edition-rework-v1) with per-check isolation.

History-grounded fixture, task family #2. The task is the REAL, underspecified
edition-rendering rework shipped in VextrumFrontend across
`778c755^ .. 225e1ef` ("vector chart and others" -> "better report formatting"
-> "citation fixes"): the before-state renders agent-authored prose verbatim, so
runs of adjacent citation links arrive as a digit-wall and raw ordered-list
markers survive into the deliverable. The rework added a deterministic text
clean-up pass ahead of the renderer.

WHY THIS FIXTURE EXISTS: every mechanism in this environment (hunk-revert
necessity probe, vacuity gate, divergence witness) claims to be LANGUAGE-
AGNOSTIC, and that claim has never been tested outside Python. This is the test.

WHAT IS GRADED: the observable output of the module's real public API,
`buildEditionDoc`. The reworked helpers are INTERNAL and unexported, so grading
them by name would require telling the agent their names -- which is exactly the
provenance leak repaired in medi-ny v2 (build_sample.py named the fix's own
functions). The agent gets discoverable CONVENTIONS and nothing else.

Assertions are SEMANTIC, never string-equality against one implementation's
output: a correct implementation is free to separate citations with a comma, a
semicolon or a middot, and must not be punished for choosing differently.

  citation-dedupe        - a source cited twice in one run renders once
  citation-cap-three     - at most three citations survive a run
  citation-run-separated - surviving citations are visually separated
  citation-dedupe-block  - the same rule holds in section bodies, not just the summary
  enum-marker-normalized - a raw "(1)" marker does not survive as literal text
  encoding-preserved     - ANCHOR (passes before AND after): accents/quotes/dashes survive
  url-integrity          - ANCHOR: an inline URL is never broken
  prose-preserved        - ANCHOR: cleaning presentation never deletes content

The three ANCHORS are green-before-green-after guards. They exist so the grader
cannot be satisfied by "change something, anything": an implementation that
mangles encoding or eats prose to make the citation checks pass still fails.

NOT GRADED, deliberately: long-paragraph chunking. Its only observable effect
here is on line positions, which depend on the recording stub's text-width
approximation -- so the dimension would measure the STUB, not the module. A
dimension we cannot attribute to the code under test is not a dimension.

Usage:  python grade.py <workspace>
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

HERE = Path(__file__).resolve().parent
WORKSPACE = Path(sys.argv[1]).resolve()
EDITION_INPUT = HERE / "edition-input.json"

checks: list[dict] = []


def record(check_id: str, weight: int, probe) -> None:
    """Every check runs inside its own boundary: a hostile candidate that raises
    fails ONE dimension rather than collapsing the whole grade into a zero."""
    try:
        outcome = probe()
        passed, detail = (outcome, "") if isinstance(outcome, bool) else outcome
    except BaseException as exc:  # noqa: BLE001 - candidates may raise anything
        passed, detail = False, f"{type(exc).__name__}: {exc}"
    checks.append({"id": check_id, "passed": bool(passed), "weight": weight,
                   "detail": str(detail)[:400]})


def render() -> dict:
    completed = subprocess.run(
        ["node", str(HERE / "drive.mjs"), str(WORKSPACE), str(EDITION_INPUT)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    if completed.returncode != 0:
        raise RuntimeError(f"render failed (exit {completed.returncode}): "
                           f"{(completed.stderr or completed.stdout)[-300:]}")
    payload = json.loads(completed.stdout.strip().splitlines()[-1])
    if "error" in payload:
        raise RuntimeError(payload["error"])
    return payload


RENDERED = render()
TOKENS: list[str] = [str(t["s"]) for t in RENDERED["text"]]
JOINED = "".join(TOKENS)
SPACED = " ".join(TOKENS)

_DIGITS = re.compile(r"^\d+$")


def marker_run_after(anchor: str) -> list[str]:
    """The citation markers rendered immediately after `anchor`.

    Citation links render as their bare number (the URL is attached as a link,
    not drawn), so a run is the digit tokens that follow the sentence, allowing
    for whatever separator the implementation chose. Reading the run positionally
    keeps this agnostic to that choice.
    """
    try:
        start = TOKENS.index(anchor) + 1
    except ValueError:
        raise AssertionError(f"the rendered document never contains {anchor!r}: "
                             "prose was lost before any citation rule could apply")
    run: list[str] = []
    for token in TOKENS[start:]:
        stripped = token.strip()
        if _DIGITS.match(stripped):
            run.append(stripped)
            continue
        if stripped in {"", ",", ";", "·", "|", "/", "-", "–"}:  # a separator, keep going
            continue
        break
    return run


def separators_after(anchor: str) -> list[str]:
    start = TOKENS.index(anchor) + 1
    seps: list[str] = []
    for token in TOKENS[start:]:
        stripped = token.strip()
        if _DIGITS.match(stripped):
            continue
        if stripped == "":
            continue
        if stripped in {",", ";", "·", "|", "/", "-", "–"}:
            seps.append(stripped)
            continue
        break
    return seps


# --- citations -------------------------------------------------------------

def probe_dedupe():
    run = marker_run_after("quarter.")
    duplicates = [m for m in set(run) if run.count(m) > 1]
    return (not duplicates,
            f"summary citation run renders {run}; repeated marker(s) {duplicates}" if duplicates
            else f"run={run}")


def probe_cap_three():
    run = marker_run_after("quarter.")
    return (len(set(run)) <= 3, f"summary citation run renders {len(set(run))} distinct citations: {run}")


def probe_separated():
    run = marker_run_after("quarter.")
    if len(run) < 2:
        return False, f"expected a multi-citation run, got {run}"
    seps = separators_after("quarter.")
    if seps:
        return True, f"citations {run} separated by {sorted(set(seps))}"
    return False, f"citations {run} render with no separator between them"


def probe_dedupe_block():
    run = marker_run_after("monthly.")
    duplicates = [m for m in set(run) if run.count(m) > 1]
    return (not duplicates,
            f"section-body citation run renders {run}; repeated marker(s) {duplicates}" if duplicates
            else f"run={run}")


# --- enumerations ----------------------------------------------------------

def probe_enum_normalized():
    literal = [t for t in TOKENS if re.fullmatch(r"\(\d+\)", t.strip())]
    return (not literal,
            f"raw ordered-list markers survive into the document as literal text: {literal}" if literal
            else "no raw (n) markers rendered")


# --- anchors: these pass BEFORE and must still pass AFTER -------------------

def probe_encoding():
    missing = [s for s in ("Éléments", "préférés", "naïve", "façade") if s not in JOINED]
    has_dash = "—" in JOINED or "–" in JOINED
    if not missing and has_dash:
        return True, "accented text and dashes survive to the page"
    return False, f"encoding regressed: missing {missing}; dash preserved={has_dash}"


def probe_url_integrity():
    """The URL must be emitted as ONE unit.

    NOT a substring test over the concatenated tokens: joining every token back
    together reassembles a URL that was torn into pieces, so such a check can
    never fail -- verified by mutation (a tokeniser splitting on dots left it
    green). "Renders intact" means the reader sees one unbroken link, i.e. it
    survives as a single drawn string.
    """
    whole = [t for t in TOKENS if "example.com/methodology.notes" in t]
    if whole:
        return True, f"the inline URL renders as one unit: {whole[0][:60]!r}"
    fragments = [t for t in TOKENS if "example.com" in t or "methodology" in t]
    return False, f"the inline URL was split across draws: {fragments[:6]}"


def probe_prose_preserved():
    required = ["Adoption", "corridor", "regulator", "consultation", "programme", "speculative"]
    missing = [word for word in required if word not in SPACED]
    if missing:
        return False, f"prose content was deleted: {missing}"
    return True, "all sampled prose content survives"


record("citation-dedupe", 2, probe_dedupe)
record("citation-cap-three", 2, probe_cap_three)
record("citation-run-separated", 1, probe_separated)
record("citation-dedupe-block", 2, probe_dedupe_block)
record("enum-marker-normalized", 2, probe_enum_normalized)
record("encoding-preserved", 1, probe_encoding)
record("url-integrity", 1, probe_url_integrity)
record("prose-preserved", 1, probe_prose_preserved)

score = round(sum(row["weight"] for row in checks if row["passed"]) * 100
              / sum(row["weight"] for row in checks)) if checks else 0
result = {"passed": score == 100, "score": score, "checks": checks}
print(json.dumps(result, ensure_ascii=False))
# The EXIT CODE is part of the grader's contract, not decoration: admission reads
# it to confirm the hidden grader actually rejects a negative control (a grader
# that exits 0 on the historical bug would "accept" it).
raise SystemExit(0 if result["passed"] else 1)
