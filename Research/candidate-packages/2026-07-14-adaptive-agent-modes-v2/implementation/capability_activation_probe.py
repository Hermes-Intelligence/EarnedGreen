#!/usr/bin/env python3
"""Behavioral, zero-provider proof that all adaptive capabilities are executable."""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from context_telemetry import analyze_run
from prepare_context import prepare
from pre_submit_gate import validate

HERE = Path(__file__).resolve().parent


def dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    checks: list[dict] = []
    with tempfile.TemporaryDirectory() as temp_name:
        root = Path(temp_name)
        task1 = root / "lean-task.md"
        task1.write_text("- Update the local documentation.\n- Preserve its example.\n", encoding="utf-8")
        lean = root / "lean/.agentic"
        lean.parent.mkdir()
        prepare(task1, root, lean, [], "mode-1-lean")
        lean_ledger = json.loads((lean / "objective-ledger.json").read_text(encoding="utf-8"))
        checks += [
            {"id":"minimal-core","pass":(lean / "core.md").is_file()},
            {"id":"compact-requirement-ledger","pass":lean_ledger.get("ledger_profile") == "compact" and len(lean_ledger.get("requirements", [])) == 2},
        ]

        task3 = root / "assured-task.md"
        task3.write_text("Continue this multi-session public API implementation with a durable checkpoint.", encoding="utf-8")
        assured = root / "assured/.agentic"
        assured.parent.mkdir()
        prepare(task3, root, assured, [], "mode-3-assured")
        ledger = json.loads((assured / "objective-ledger.json").read_text(encoding="utf-8"))
        evidence = json.loads((assured / "evidence.json").read_text(encoding="utf-8"))
        impact = json.loads((assured / "impact-map.json").read_text(encoding="utf-8"))
        checkpoint = json.loads((assured / "checkpoint.json").read_text(encoding="utf-8"))
        handoff = json.loads((assured / "session-handoff.json").read_text(encoding="utf-8"))
        blocked = validate(ledger, evidence, root, impact_map=impact, checkpoint=checkpoint, handoff=handoff, reexecute=False)
        proof = root / "proof.txt"
        proof.write_text("behavior proof", encoding="utf-8")
        requirements = {row["id"]: row for row in ledger["requirements"]}
        for row in evidence["requirements"]:
            items = [{"kind":"behavior","path":"proof.txt"}]
            for kind in requirements[row["requirement_id"]].get("evidence_required", []):
                if kind == "behavior":
                    continue
                items.append({"kind":kind, "command":["python", "-c", "pass"], "exit_code":0} if kind in {"test","migration"} else {"kind":kind,"path":"proof.txt"})
            row.update({"status":"verified", "evidence":items})
        evidence["verification_runs"] = [{"command":["python", "-c", "pass"], "exit_code":0}]
        evidence["adversarial_verification"] = {"status":"PASS", "threat_model":["unknown consumer", "malformed input"], "verification_runs":[{"command":["python", "-c", "pass"], "exit_code":0}]}
        evidence["completion_claim"] = {"status":"ready", "summary":"probe"}
        for row in impact["sections"].values():
            row.update({"status":"verified", "evidence":["proof.txt"]})
        checkpoint.update({"status":"ready", "evidence_refs":["proof.txt"], "next_action":"Run final integration check"})
        handoff.update({"status":"ready", "verified_state":["requirements evidenced"], "next_action":"Run final integration check"})
        passed = validate(ledger, evidence, root, impact_map=impact, checkpoint=checkpoint, handoff=handoff, reexecute=False)
        checks += [
            {"id":"impact-map","pass":all(row["status"] == "verified" for row in impact["sections"].values())},
            {"id":"adversarial-verification","pass":blocked["verdict"] == "FAIL" and passed["verdict"] == "PASS"},
            {"id":"durable-checkpoints","pass":checkpoint["required"] and checkpoint["status"] == "ready"},
            {"id":"session-handoff-state","pass":handoff["required"] and handoff["status"] == "ready"},
        ]

        run = root / "telemetry-probe"
        (run / "workspace/.agentic").mkdir(parents=True)
        dump(run / "workspace/.agentic/context-manifest.json", {"modules":[{"id":"change-impact"}]})
        (run / "workspace/.agentic/core.md").write_text("core", encoding="utf-8")
        (run / "workspace/.agentic/provider-events.jsonl").write_text("opened .agentic/core.md and .agentic/modules/change-impact.md; checked call sites", encoding="utf-8")
        dump(run / "run-record.json", {"case_id":"probe", "arm":"mode-3-assured", "token_usage":{"total_observed_tokens":0}})
        telemetry = analyze_run(run, {"change-impact":["call sites"]})
        checks.append({"id":"context-usage-telemetry","pass":telemetry["core"]["opened"] and telemetry["opened_count"] == 1 and telemetry["action_linked_count"] == 1})

    result = {"schema_version":1, "verdict":"PASS" if all(row["pass"] for row in checks) else "FAIL", "provider_calls":0, "checks":checks}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    dump(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
