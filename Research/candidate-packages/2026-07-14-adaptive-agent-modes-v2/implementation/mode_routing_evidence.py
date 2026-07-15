#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from adaptive_router import route

HERE = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cases = json.loads((HERE / "tests/mode-cases.json").read_text(encoding="utf-8"))["cases"]
    rows = []
    for case in cases:
        result = route(case["task"], case.get("changed_paths"))
        selected = {row["id"] for row in result["selected_modules"]}
        failures = []
        if result["mode"] != case["expected_mode"]:
            failures.append(f"mode {result['mode']} != {case['expected_mode']}")
        failures += [f"missing module {item}" for item in sorted(set(case["required"]) - selected)]
        failures += [f"forbidden module {item}" for item in sorted(set(case["forbidden"]) & selected)]
        rows.append({"id": case["id"], "verdict": "PASS" if not failures else "FAIL", "mode": result["mode"], "selected_modules": sorted(selected), "failures": failures})
    result = {"schema_version": 2, "verdict": "PASS" if all(row["verdict"] == "PASS" for row in rows) else "FAIL", "provider_calls": 0, "cases": rows}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
