#!/usr/bin/env python3
"""Executable runner for tests/mode-cases.json.

Loads every declared routing case, runs it through adaptive_router.route, and
asserts the expected mode plus the required/forbidden knowledge modules. Prints a
per-case summary and exits non-zero if any case fails, so the mode taxonomy is no
longer inert JSON.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
IMPL = HERE.parent
sys.path.insert(0, str(IMPL))

from adaptive_router import route  # noqa: E402


def evaluate(case: dict) -> tuple[bool, str, dict]:
    result = route(case["task"], case.get("changed_paths"))
    selected = {row["id"] for row in result["selected_modules"]}
    mode_ok = result["mode"] == case["expected_mode"]
    required = set(case.get("required", []))
    forbidden = set(case.get("forbidden", []))
    missing_required = required - selected
    present_forbidden = forbidden & selected
    surfaced = {row["id"] for row in result.get("relevant_findings", {}).get("findings", [])}
    missing_findings = set(case.get("expected_findings", [])) - surfaced
    ok = mode_ok and not missing_required and not present_forbidden and not missing_findings
    reasons = []
    if not mode_ok:
        reasons.append(f"mode {result['mode']} != expected {case['expected_mode']}")
    if missing_required:
        reasons.append(f"missing required modules: {sorted(missing_required)}")
    if present_forbidden:
        reasons.append(f"forbidden modules present: {sorted(present_forbidden)}")
    if missing_findings:
        reasons.append(f"findings not surfaced at decision time: {sorted(missing_findings)}")
    detail = {"mode": result["mode"], "selected": sorted(selected), "findings": sorted(surfaced)}
    return ok, "; ".join(reasons), detail


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    cases = json.loads((HERE / "mode-cases.json").read_text(encoding="utf-8-sig"))["cases"]
    passed = 0
    failures: list[str] = []
    for case in cases:
        ok, reason, detail = evaluate(case)
        marker = "PASS" if ok else "FAIL"
        print(f"[{marker}] {case['id']:24} mode={detail['mode']:14} modules={detail['selected']}")
        if ok:
            passed += 1
        else:
            failures.append(f"{case['id']}: {reason}")
    print(f"\n{passed}/{len(cases)} mode cases passed.")
    if failures:
        print("\nFailures:")
        for line in failures:
            print(f"  - {line}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
