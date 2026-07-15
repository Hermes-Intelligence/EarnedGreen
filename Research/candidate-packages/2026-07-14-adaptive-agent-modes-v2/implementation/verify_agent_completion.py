#!/usr/bin/env python3
"""Host-side acceptance gate for an adaptive run, separate from the hidden grader."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((args.run / "run-manifest.json").read_text(encoding="utf-8-sig"))
    arm = manifest["arm"]
    failures = []
    result_path = args.run / "workspace" / ".agentic" / "pre-submit-result.json"
    if arm != "vanilla":
        if not result_path.exists():
            failures.append("missing pre-submit-result.json")
        else:
            result = json.loads(result_path.read_text(encoding="utf-8-sig"))
            if result.get("verdict") != "PASS" or not result.get("completion_allowed"):
                failures.append("pre-submit gate did not pass")
    result = {
        "schema_version": 2,
        "arm": arm,
        "verdict": "PASS" if not failures else "FAIL",
        "failures": failures,
        "hidden_grader_used": False,
        "meaning": "The agent may finish the run; product quality is scored separately by the isolated hidden grader."
    }
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if not failures else 1)


if __name__ == "__main__":
    main()
