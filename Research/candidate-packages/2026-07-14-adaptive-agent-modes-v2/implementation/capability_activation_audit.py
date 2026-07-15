#!/usr/bin/env python3
"""Fail closed when a declared mode capability is only a label."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CANDIDATE = HERE.parent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    modes = json.loads((HERE / "modes.json").read_text(encoding="utf-8-sig"))
    contract = json.loads((HERE / "capability-activation-contract.json").read_text(encoding="utf-8-sig"))
    probe_path = args.output.parent / "capability-activation-probe.json"
    probe = subprocess.run([sys.executable, str(HERE / "capability_activation_probe.py"), "--output", str(probe_path)], cwd=HERE, text=True, capture_output=True, encoding="utf-8", errors="replace", timeout=120)
    declared = {cap for mode in modes["modes"] for cap in mode.get("capabilities", [])}
    rows = {row["id"]: row for row in contract["capabilities"]}
    failures = []
    unknown = sorted(declared - set(rows))
    stale = sorted(set(rows) - declared)
    if unknown:
        failures.append({"id":"unregistered-capabilities","items":unknown})
    if stale:
        failures.append({"id":"stale-capability-contract","items":stale})
    if probe.returncode != 0:
        failures.append({"id":"behavioral-activation-probe","status":"FAIL","stdout":probe.stdout[-2000:],"stderr":probe.stderr[-2000:]})
    for capability in sorted(declared & set(rows)):
        row = rows[capability]
        missing_paths = [path for path in row.get("evidence_paths", []) if not (CANDIDATE / path).is_file()]
        if missing_paths:
            failures.append({"id":capability,"status":"invalid-evidence","missing_paths":missing_paths})
        elif row.get("status") != "active":
            failures.append({"id":capability,"status":row.get("status"),"reason":row.get("reason")})
    result = {
        "schema_version":2,
        "verdict":"PASS" if not failures else "FAIL",
        "provider_calls":0,
        "declared_capabilities":len(declared),
        "active_capabilities":sum(rows[cap].get("status") == "active" for cap in declared if cap in rows),
        "failures":failures,
        "behavioral_probe":"capability-activation-probe.json",
        "rule":"every capability declared by a mode must be active, backed by existing evidence paths, and pass a zero-provider behavioral probe before provider comparison"
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if not failures else 1)


if __name__ == "__main__":
    main()
