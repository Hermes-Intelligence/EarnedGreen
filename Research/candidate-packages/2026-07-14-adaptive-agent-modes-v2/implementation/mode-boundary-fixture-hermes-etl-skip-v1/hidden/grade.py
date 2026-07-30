#!/usr/bin/env python3
"""MECHANICAL held-out grader: frozen diff-derived predicates, no hand-written dimensions.

The first grader in this programme whose expectations were not written by a
mind: every predicate in hidden/derived-predicates.json was derived from the
real before/after behaviour diff of HermesAirflow 37423b0 over the scenario
corpus, with an altformat variant filtering implementation-pinning candidates
(see build_etl_oracle.py). This file only EXECUTES them.

Dimensions = scenario families (one reported check per family; a family passes
iff every one of its predicates holds). The grader NEVER collapses: whatever
the workspace does — including refusing to import, which the admission gate's
hostile battery makes it do — every declared dimension is reported, failed
dimensions carry their reason, and the exit code is non-zero unless everything
passed.

Usage: python grade.py <workspace>   (exit 0 iff score == 100)
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNNER_TIMEOUT = 120

# The evaluation vocabulary must match the derivation vocabulary exactly, so
# the projections are imported from the same module that derived the predicates.
sys.path.insert(0, str(HERE.parent.parent))
try:
    from diff_oracle import PROJECTIONS
except ImportError:  # standalone copy of the fixture: minimal local vocabulary
    PROJECTIONS = {
        "seq": lambda s: list(s),
        "multiset": lambda s: sorted(s),
        "uniq": lambda s: sorted(set(s)),
        "bigrams": lambda s: sorted({f"{a}␟{b}" for a, b in zip(s, s[1:])}),
        "joined": lambda s: " ".join(s),
        "count": lambda s: len(s),
        "charset": lambda s: sorted(set("".join(s))),
    }


def capture(workspace: Path) -> dict:
    try:
        completed = subprocess.run(
            [sys.executable, str(HERE / "etl_runner.py"), str(HERE / "scenarios.json")],
            cwd=workspace, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=RUNNER_TIMEOUT)
        if completed.returncode != 0:
            return {"__runner_error__": completed.stderr[-400:]}
        return json.loads(completed.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as error:
        return {"__runner_error__": f"{type(error).__name__}: {error}"}


def main() -> None:
    workspace = Path(sys.argv[1]).resolve()
    spec = json.loads((HERE / "derived-predicates.json").read_text(encoding="utf-8-sig"))
    predicates = spec["discriminating"] + spec["preserving"]
    families = sorted({pred["family"] for pred in predicates})
    streams = capture(workspace)

    failures_by_family: dict[str, list[str]] = {family: [] for family in families}
    runner_error = streams.get("__runner_error__")
    for pred in predicates:
        family = pred["family"]
        if runner_error:
            failures_by_family[family].append(f"{pred['id']}: runner failed: {runner_error[:120]}")
            continue
        stream = streams.get(pred["input_id"])
        if not isinstance(stream, list):
            reason = (stream or {}).get("__error__", "no stream") if isinstance(stream, dict) else "no stream"
            failures_by_family[family].append(f"{pred['id']}: {reason[:160]}")
            continue
        actual = PROJECTIONS[pred["projection"]](stream)
        if actual != pred["expected"]:
            failures_by_family[family].append(
                f"{pred['id']}: projection {pred['projection']} diverges from the derived expectation")

    checks = []
    for family in families:
        failing = failures_by_family[family]
        checks.append({"id": family, "passed": not failing, "weight": 1,
                       "detail": "; ".join(failing[:4]) if failing else "all derived predicates hold"})
    passed_count = sum(1 for row in checks if row["passed"])
    score = round(100 * passed_count / len(checks))
    result = {
        "schema_version": 1,
        "score": score,
        "passed": passed_count == len(checks),
        "checks": checks,
        "grader": "mechanical (diff-derived predicates; see hidden/derived-predicates.json)",
    }
    # ONE line, ASCII-safe: the admission harness recovers the grader's JSON by
    # scanning output lines, and a pretty-printed object is invisible to it.
    print(json.dumps(result, ensure_ascii=True))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
