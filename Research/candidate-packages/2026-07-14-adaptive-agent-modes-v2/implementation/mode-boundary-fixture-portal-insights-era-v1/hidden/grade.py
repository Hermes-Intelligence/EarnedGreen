#!/usr/bin/env python3
"""MECHANICAL held-out GEN-4 grader for the portal insights era fixture.

Executes hidden/derived-predicates.json — relational predicates
(kinds-superset, count-direction, count-equal for state-write kinds) derived
by build_portal_oracle_gen4.py from the real 26-commit insights era,
plus exact seq preservation guards. Dimensions = families; a family passes iff
all its predicates hold; the grader NEVER collapses (hostile workspaces get
every dimension reported as failed, with reasons).
Usage: python grade.py <workspace>; exit 0 iff score == 100.
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DRIVER_TIMEOUT = 300


def _kinds(stream):
    return {p.split(":", 1)[0] for p in stream}


def _kind_count(stream, kind):
    return sum(1 for p in stream if p.split(":", 1)[0] == kind)


def _direction_holds(direction, baseline, n):
    if direction == "became-nonzero":
        return n > 0
    if direction == "became-zero":
        return n == 0
    if direction == "increased":
        return n > baseline
    if direction == "decreased":
        return n < baseline
    raise ValueError(direction)


def predicate_holds(pred, stream) -> bool:
    relation = pred.get("relation", "equal")
    if relation == "equal":
        if pred["projection"] != "seq":
            raise ValueError(f"unexpected exact projection {pred['projection']!r}")
        return list(stream) == pred["expected"]
    if relation == "kinds-superset":
        return set(pred["expected"]) <= _kinds(stream)
    if relation == "count-direction":
        return _direction_holds(pred["direction"], pred["baseline"],
                                _kind_count(stream, pred["kind"]))
    if relation == "count-equal":
        return _kind_count(stream, pred["kind"]) == pred["expected"]
    raise ValueError(f"unknown relation {relation!r}")


def capture(workspace: Path) -> dict:
    try:
        completed = subprocess.run(
            [sys.executable, str(HERE / "portal_driver.py"), str(HERE / "corpus.json")],
            cwd=workspace, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=DRIVER_TIMEOUT)
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

    failures: dict[str, list[str]] = {family: [] for family in families}
    runner_error = streams.get("__runner_error__")
    for pred in predicates:
        family = pred["family"]
        if runner_error:
            failures[family].append(f"{pred['id']}: driver failed: {runner_error[:120]}")
            continue
        stream = streams.get(pred["input_id"])
        if not isinstance(stream, list):
            failures[family].append(f"{pred['id']}: no stream for scenario")
            continue
        try:
            holds = predicate_holds(pred, stream)
        except ValueError as error:
            failures[family].append(f"{pred['id']}: grader spec error: {error}")
            continue
        if not holds:
            failures[family].append(f"{pred['id']}: relation does not hold on the emitted stream")

    checks = [{"id": family, "passed": not failures[family], "weight": 1,
               "detail": "; ".join(failures[family][:4]) if failures[family] else "all derived predicates hold"}
              for family in families]
    passed_count = sum(1 for row in checks if row["passed"])
    score = round(100 * passed_count / len(checks))
    result = {"schema_version": 1, "score": score, "passed": passed_count == len(checks),
              "checks": checks,
              "ungraded_named_dimensions": spec.get("ungraded_named_dimensions", []),
              "grader": "mechanical GEN-4 (relational dataflow-era predicates; see hidden/derived-predicates.json)"}
    print(json.dumps(result, ensure_ascii=True))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()

