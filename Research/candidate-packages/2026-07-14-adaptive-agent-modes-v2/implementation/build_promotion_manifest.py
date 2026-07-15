#!/usr/bin/env python3
"""Build a hash-locked, approval-pending promotion manifest for this Candidate."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CANDIDATE = HERE.parent


def repo_root() -> Path:
    for parent in HERE.parents:
        if (parent / "Runtime/stable/manifest.json").exists():
            return parent
    raise RuntimeError("repository root not found")


REPO = repo_root()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


MAPPINGS = [
    ("promotion/payload/Runtime/stable/manifest.json", "Runtime/stable/manifest.json"),
    ("implementation/modes.json", "Runtime/adaptive-modes.json"),
    ("promotion/payload/Router/catalog/modules.json", "Router/catalog/modules.json"),
    ("implementation/adaptive_router.py", "tools/adaptive_router.py"),
    ("implementation/objective_compiler.py", "tools/objective_compiler.py"),
    ("implementation/pre_submit_gate.py", "tools/pre_submit_gate.py"),
    ("implementation/prepare_context.py", "tools/prepare_context.py"),
    ("implementation/resolve_capability_profile.py", "tools/resolve_capability_profile.py"),
    ("implementation/prepare_adaptive_run.py", "tools/prepare_adaptive_run.py"),
    ("implementation/verify_agent_completion.py", "tools/verify_agent_completion.py"),
    ("implementation/new_ablation_campaign.py", "tools/new_adaptive_ablation_campaign.py"),
    ("implementation/failure_attribution.py", "Evals/tools/attribute-failure.py"),
    ("implementation/context_telemetry.py", "Evals/tools/context-telemetry.py"),
    ("implementation/grade_adaptive_run.py", "Evals/tools/grade-adaptive-run.py"),
    ("implementation/capability_activation_audit.py", "Evals/tools/capability-activation-audit.py"),
    ("implementation/capability_activation_probe.py", "Evals/tools/capability-activation-probe.py"),
    ("implementation/capability-activation-contract.json", "Runtime/capability-activation-contract.json"),
    ("implementation/mode_boundary_fixture_validity.py", "Evals/tools/mode-boundary-fixture-validity.py"),
    ("implementation/fixture_admission.py", "Evals/tools/fixture-admission.py"),
    ("implementation/eval_validity.py", "Evals/tools/eval-validity.py"),
    ("implementation/schemas/objective-ledger.schema.json", "Core/schemas/objective-ledger.schema.json"),
    ("promotion/payload/tools/route.ps1", "tools/route.ps1"),
    ("implementation/modules/objective-integrity.md", "Core/knowledge-modules/objective-integrity.md"),
    ("implementation/modules/reliability-contract.md", "Core/knowledge-modules/reliability-contract.md"),
    ("promotion/payload/Setup/adaptive-modes.md", "Setup/adaptive-modes.md"),
    ("promotion/payload/Setup/adaptive-modes.pdf", "Setup/adaptive-modes.pdf"),
]

for fixture_file in sorted((HERE / "mode-boundary-fixture").rglob("*")):
    if fixture_file.is_file():
        relative = fixture_file.relative_to(HERE / "mode-boundary-fixture").as_posix()
        MAPPINGS.append((f"implementation/mode-boundary-fixture/{relative}", f"Evals/fixtures/adaptive-contract-evolution-v2/{relative}"))


def main() -> None:
    files = []
    for source_rel, target_rel in MAPPINGS:
        source = CANDIDATE / source_rel
        target = REPO / target_rel
        if not source.is_file():
            raise RuntimeError(f"missing promotion source: {source_rel}")
        files.append({
            "source": source_rel,
            "target": target_rel,
            "before_sha256": sha(target) if target.is_file() else None,
            "after_sha256": sha(source),
        })
    run_manifest = json.loads((CANDIDATE / "run-manifest.json").read_text(encoding="utf-8-sig"))
    result = {
        "schema_version": 1,
        "candidate_id": CANDIDATE.name,
        "release": "0.2.0-adaptive-modes",
        "status": "awaiting-outcome-eval",
        "stable_manifest_before_sha256": run_manifest["stable_manifest_sha256"],
        "required_evals": [{"report":"evidence/candidate-eval-summary.json","minimum_passed":12,"maximum_failed":0}],
        "files": files,
        "approval": {"approved": False, "approved_by": None, "approved_at": None, "blocked_by":"valid comparative outcome screen not completed; first six-call screen was invalidated by control-prompt and host/WSL gate confounders"},
        "rollback": "generated automatically by tools/promote-candidate.ps1 if and only if approved",
        "provider_calls_authorized": 0,
    }
    output = CANDIDATE / "promotion/manifest.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status":result["status"],"files":len(files),"provider_calls_authorized":0},indent=2))


if __name__ == "__main__":
    main()
