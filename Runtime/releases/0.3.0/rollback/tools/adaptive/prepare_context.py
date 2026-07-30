#!/usr/bin/env python3
"""Compile the smallest mode-specific agent context and executable completion gate."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

from adaptive_router import route
from objective_compiler import compact_ledger, compile_ledger
from spec_synthesis import compile_spec, render_spec_md

HERE = Path(__file__).resolve().parent


def repo_root() -> Path:
    for parent in (HERE, *HERE.parents):
        if (parent / "Runtime/stable/manifest.json").exists():
            return parent
    raise RuntimeError("AgenticWorkBestPractices root not found")


REPO = repo_root()
CANDIDATE = HERE.parent if (HERE.parent / "run-manifest.json").exists() else REPO


def dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def source_path(relative: str) -> Path:
    if relative.startswith("implementation/"):
        return CANDIDATE / relative
    return REPO / relative


def prepare(task_path: Path, workspace: Path, output: Path, changed_paths: list[str], forced_mode: str | None = None) -> dict:
    task = task_path.read_text(encoding="utf-8-sig")
    ledger = compile_ledger(task, str(task_path))
    decision = route(task, changed_paths, forced_mode)
    if not forced_mode:
        modes_path = HERE / "modes.json"
        if not modes_path.exists():
            modes_path = REPO / "Runtime/adaptive-modes.json"
        mode_policy = json.loads(modes_path.read_text(encoding="utf-8-sig"))["modes"]
        current_rank = decision["mode_rank"]
        # Compiled scope (requirement/file counts) is the breadth axis: it may raise
        # the mode but never past the breadth escalation ceiling (mode-3-assured).
        # Only consequence signals, handled inside the router, can select full.
        ceiling_rank = max((m["rank"] for m in mode_policy if m.get("breadth_escalation_ceiling")), default=3)
        needed_rank = next(
            mode["rank"] for mode in mode_policy
            if mode["rank"] >= current_rank
            and len(ledger["requirements"]) <= mode["selection"]["max_requirement_count"]
            and len(changed_paths) <= mode["selection"]["max_changed_files"]
        )
        needed_rank = min(needed_rank, max(current_rank, ceiling_rank))
        needed = next(mode["id"] for mode in mode_policy if mode["rank"] == needed_rank)
        if needed != decision["mode"]:
            decision = route(task, changed_paths, minimum_mode=needed)
    output.mkdir(parents=True, exist_ok=True)
    dump(output / "mode-decision.json", decision)
    # Decision-time research surfacing: when the task is a design/benchmark/
    # architecture decision, the Context Pack carries the topic-matched findings
    # explicitly so the agent reads the research that bears on the decision.
    findings_section = decision.get("relevant_findings") or {}
    if findings_section.get("findings"):
        dump(output / "relevant-findings.json", findings_section)
    if decision["mode"] == "vanilla":
        (output / "agent_prompt_appendix.txt").write_text("Read-only/trivial mode selected. Do not mutate files.\n", encoding="utf-8")
        return {"mode": "vanilla", "context_characters": 0, "requirements": 0, "modules": []}

    mode_rank = decision["mode_rank"]
    agent_ledger = compact_ledger(ledger) if decision["mode"] == "mode-1-lean" else ledger
    dump(output / "objective-ledger.json", agent_ledger)
    shutil.copyfile(REPO / "Core/runtime.md", output / "core.md")
    evidence = {
        "schema_version": 2,
        "mode": decision["mode"],
        "capabilities": decision["capabilities"],
        "requirements": [{"requirement_id": row["id"], "status": "pending", "reason": None, "evidence": []} for row in ledger["requirements"]],
        "ambiguity_resolutions": [],
        "verification_runs": [],
        "adversarial_verification": {"status": "not-required", "threat_model": [], "verification_runs": []},
        "scope_approval": {"status": "not-required", "approved_by": None, "scope": None},
        "independent_verification": {"status": "not-required", "verifier_profile": None, "evidence": []},
        "completion_claim": {"status": "in_progress", "summary": None}
    }
    dump(output / "evidence.json", evidence)

    axes = decision.get("analysis", {}).get("axes", decision.get("axes", {}))
    continuity_required = axes.get("continuity") == "multi-session"
    breadth_wide = axes.get("breadth") == "wide"
    checkpoint_required = mode_rank >= 3 and (continuity_required or breadth_wide)
    if mode_rank >= 3:
        dump(output / "impact-map.json", {
            "schema_version": 1,
            "mode": decision["mode"],
            "sections": {
                key: {"status": "pending", "evidence": [], "reason": None}
                for key in ("definitions", "consumers", "tests", "compatibility", "documentation", "observability")
            },
        })
        evidence["adversarial_verification"] = {"status": "pending", "threat_model": [], "verification_runs": []}
        dump(output / "checkpoint.json", {
            "schema_version": 1, "required": checkpoint_required,
            "status": "pending" if checkpoint_required else "not-required",
            "objective_id": ledger["task_sha256"], "completed_requirements": [],
            "evidence_refs": [], "decisions": [], "blockers": [], "next_action": None,
        })
        dump(output / "session-handoff.json", {
            "schema_version": 1, "required": checkpoint_required,
            "status": "pending" if checkpoint_required else "not-required",
            "resume_from": None, "verified_state": [], "pending_requirements": [row["id"] for row in ledger["requirements"]],
            "next_action": None, "forbidden_assumptions": [],
        })
        dump(output / "evidence.json", evidence)

    protected = []
    test_files = (
        sorted(path for path in (workspace / "tests").rglob("*") if path.is_file())
        if (workspace / "tests").exists()
        else []
    )
    for path in [task_path, *test_files]:
        if path.is_file():
            protected.append({"path": path.resolve().relative_to(workspace.resolve()).as_posix(), "sha256": digest(path)})
    baseline = {"schema_version": 1, "protected_files": protected}
    dump(output / "baseline.json", baseline)

    module_dir = output / "modules"
    module_dir.mkdir(exist_ok=True)
    copied = []
    context_characters = 0
    for module in decision["selected_modules"]:
        source = source_path(module["path"])
        target = module_dir / f"{module['id']}.md"
        shutil.copyfile(source, target)
        size = len(target.read_text(encoding="utf-8-sig"))
        context_characters += size
        copied.append({"id": module["id"], "path": target.relative_to(output).as_posix(), "characters": size, "reasons": module["reasons"], "outcome_markers": module["outcome_markers"]})
    if context_characters > decision["context_budget"]["max_characters"]:
        raise RuntimeError("Compiled context exceeds the selected mode budget")
    shutil.copyfile(HERE / "pre_submit_gate.py", output / "pre_submit_gate.py")

    # Spec-first planning phase for underspecified tasks (clarity axis): drop the
    # spec scaffold plus the tooling the agent and the gate need to validate and
    # freeze it. The frozen ledger is the anti-scope-shrink completion boundary.
    spec_first = "spec-synthesis" in decision["capabilities"]
    if spec_first:
        spec = compile_spec(task, str(task_path))
        dump(output / "spec.json", spec)
        (output / "spec.md").write_text(render_spec_md(spec), encoding="utf-8")
        shutil.copyfile(HERE / "spec_synthesis.py", output / "spec_synthesis.py")
        shutil.copyfile(HERE / "objective_compiler.py", output / "objective_compiler.py")
        shutil.copyfile(HERE / "modules" / "risk-discovery.md", output / "risk-discovery.md")
    (output / "run-pre-submit.ps1").write_text(
        "$ErrorActionPreference='Stop'\n"
        "$python=(Get-Command python -ErrorAction SilentlyContinue)\n"
        "if($python){& $python.Source .agentic/pre_submit_gate.py --ledger .agentic/objective-ledger.json --evidence .agentic/evidence.json --workspace . --baseline .agentic/baseline.json --output .agentic/pre-submit-result.json; exit $LASTEXITCODE}\n"
        "$py=(Get-Command py -ErrorAction Stop).Source\n"
        "& $py -3 .agentic/pre_submit_gate.py --ledger .agentic/objective-ledger.json --evidence .agentic/evidence.json --workspace . --baseline .agentic/baseline.json --output .agentic/pre-submit-result.json\n"
        "exit $LASTEXITCODE\n",
        encoding="utf-8",
    )
    (output / "run-pre-submit.sh").write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        "python3 .agentic/pre_submit_gate.py --ledger .agentic/objective-ledger.json --evidence .agentic/evidence.json --workspace . --baseline .agentic/baseline.json --output .agentic/pre-submit-result.json\n",
        encoding="utf-8",
    )
    completion_requires = ["objective ledger fully evidenced", "material ambiguities resolved", "verification commands pass", "protected inputs unchanged", "pre-submit-result verdict PASS"]
    if mode_rank >= 3:
        completion_requires += ["impact map complete", "adversarial verification passes"]
    if checkpoint_required:
        completion_requires += ["durable checkpoint ready", "session handoff ready"]
    if spec_first:
        completion_requires += [
            "spec validated (spec_synthesis validate PASS) and freeze recorded in spec-freeze.json",
            "ledger freeze intact: no frozen requirement removed, rewritten or downgraded without an owner_scope_change entry",
            "every spec acceptance test re-executed by the gate and passing",
        ]
    enforcement = {
        "schema_version": 2,
        "mode": decision["mode"],
        "hard_gate": True,
        "completion_commands": {"windows": "powershell -ExecutionPolicy Bypass -File .agentic/run-pre-submit.ps1", "posix": "bash .agentic/run-pre-submit.sh"},
        "completion_requires": completion_requires,
        "host_hidden_grader_is_not_agent_completion_evidence": True,
        "independent_verifier_required": decision["mode"] == "full",
        "human_gate": decision["model_routing"]["human_gate"]
    }
    if decision["mode"] == "full":
        evidence["scope_approval"] = {"status": "pending", "approved_by": None, "scope": None}
        evidence["independent_verification"] = {
            "status": "pending",
            "verifier_profile": decision["model_routing"]["verifier_profile"],
            "evidence": []
        }
        dump(output / "evidence.json", evidence)
    dump(output / "enforcement.json", enforcement)
    dump(output / "context-manifest.json", {"schema_version": 3, "mode": decision["mode"], "core": "core.md", "ledger_profile": agent_ledger.get("ledger_profile", "full"), "modules": copied, "context_characters": context_characters, "context_budget": decision["context_budget"], "requirement_count": len(ledger["requirements"]), "checkpoint_required": checkpoint_required, "spec_first": spec_first})
    prompt = (
        f"Adaptive mode: {decision['mode']}. Read .agentic/core.md, then only the selected files under .agentic/modules. "
        "Before editing, review .agentic/objective-ledger.json and resolve material ambiguities. "
        + ("SPEC-FIRST CONTRACT: this task is underspecified; its real requirements live in the codebase's implicit conventions. "
           "Before ANY mutation: explore the workspace critically, anticipate failure modes, and fill .agentic/spec.json "
           "(surface inventory derived from the code, convention inventory with file evidence, decision points pinned by evidence "
           "or escalated to the owner, risk register with runnable verifications, acceptance tests, frozen requirement ledger). "
           "Read .agentic/risk-discovery.md for failure modes that really happened - an illustrative, never exhaustive list. "
           "Then run: python .agentic/spec_synthesis.py validate --spec .agentic/spec.json --workspace . --task-file <task> --freeze .agentic/spec-freeze.json. "
           "The validated spec freezes the requirement ledger: completion means the FULL frozen scope actually works and every "
           "acceptance test passes when the gate re-executes it. Silently narrowing scope fails the gate; scope may only shrink "
           "through an owner_scope_changes entry recording explicit human approval. Additions are always allowed. "
           if spec_first else "")
        + "During work, update .agentic/evidence.json with reproducible evidence for every requirement. "
        "Before claiming completion, run the platform command in .agentic/enforcement.json; a FAIL blocks completion. "
        + ("Complete .agentic/impact-map.json and record an adversarial threat model plus re-executable challenge runs in .agentic/evidence.json. " if mode_rank >= 3 else "")
        + ("Before a session boundary, make .agentic/checkpoint.json and .agentic/session-handoff.json ready and evidence-backed. " if checkpoint_required else "")
        + "The host hidden grader is evaluation evidence after the run, never a substitute for the pre-submit gate.\n"
    )
    (output / "agent_prompt_appendix.txt").write_text(prompt, encoding="utf-8")
    return {"mode": decision["mode"], "context_characters": context_characters, "requirements": len(ledger["requirements"]), "modules": [row["id"] for row in copied]}


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-file", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--changed-path", action="append", default=[])
    parser.add_argument("--force-mode", choices=["vanilla","mode-1-lean","mode-2-routed","mode-3-assured","full"])
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    task_path = args.task_file if args.task_file.is_absolute() else workspace / args.task_file
    output = args.output_dir or workspace / ".agentic"
    print(json.dumps(prepare(task_path.resolve(), workspace, output.resolve(), args.changed_path, args.force_mode), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
