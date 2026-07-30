#!/usr/bin/env python3
"""MECHANICAL held-out grader for the era fixture (pattern: hermes-etl-skip-v1).

Executes hidden/derived-predicates.json — predicates derived from the real
four-commit era diff by build_era_oracle.py, altformat-filtered, with a
per-family projection policy that keeps every expectation implementation-
agnostic (kindset for charts, textseq for text, count for citation runs).
Dimensions = families; a family passes iff all its predicates hold; the grader
NEVER collapses (hostile workspaces get every dimension reported as failed,
with reasons). Usage: python grade.py <workspace>; exit 0 iff score == 100.
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DRIVER_TIMEOUT = 120

sys.path.insert(0, str(HERE.parent.parent))
try:
    from diff_oracle import PROJECTIONS
except ImportError:
    PROJECTIONS = {
        "seq": lambda s: list(s), "multiset": lambda s: sorted(s), "uniq": lambda s: sorted(set(s)),
        "bigrams": lambda s: sorted({f"{a}␟{b}" for a, b in zip(s, s[1:])}),
        "joined": lambda s: " ".join(s), "count": lambda s: len(s),
        "charset": lambda s: sorted(set("".join(s))),
        "kindset": lambda s: sorted({p.split(":", 1)[0] for p in s}),
        "textseq": lambda s: [p for p in s if p.startswith("text:")],
    }


def capture(workspace: Path) -> dict:
    try:
        completed = subprocess.run(
            ["node", str(HERE / "edition_driver.mjs"), str(HERE / "corpus.json"), "src/editionPdf.js"],
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
            reason = (stream or {}).get("__error__", "no stream") if isinstance(stream, dict) else "no stream"
            failures[family].append(f"{pred['id']}: {reason[:160]}")
            continue
        if PROJECTIONS[pred["projection"]](stream) != pred["expected"]:
            failures[family].append(f"{pred['id']}: projection {pred['projection']} diverges from the derived expectation")

    checks = [{"id": family, "passed": not failures[family], "weight": 1,
               "detail": "; ".join(failures[family][:4]) if failures[family] else "all derived predicates hold"}
              for family in families]
    passed_count = sum(1 for row in checks if row["passed"])
    score = round(100 * passed_count / len(checks))
    result = {"schema_version": 1, "score": score, "passed": passed_count == len(checks),
              "checks": checks,
              "ungraded_named_dimensions": spec.get("ungraded_named_dimensions", []),
              "grader": "mechanical (era diff-derived predicates; see hidden/derived-predicates.json)"}
    print(json.dumps(result, ensure_ascii=True))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
