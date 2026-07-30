#!/usr/bin/env python3
"""Compile the smallest mode-specific agent context and executable completion gate.

Schema 4: artifacts are CAPABILITY-driven, not rank-driven. The router decides
the mode (lite / standard / critical) and the conditional capabilities; this
module materializes exactly the artifacts those capabilities need:

  objective-ledger / compact-requirement-ledger   the requirement ledger
  pre-submit-gate                                 gate script + enforcement.json
  verification-loop                               baseline snapshot + frozen
                                                  check suite + loop tooling
  spec-synthesis                                  spec scaffold + freeze tooling
  durable-checkpoints / session-handoff-state     checkpoint + handoff artifacts
  independent-verifier / human-approval-boundaries  critical-mode evidence slots
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

from adaptive_router import route
from harness_checks import harness_freeze_sha256, snapshot_baseline
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


def compile_check_suite(workspace: Path, spec_first: bool, include_symbol_sweep: bool = True,
                        harness_dir: Path | None = None, script_home: Path | None = None) -> dict:
    """Author the independent check suite the verification loop and gate run.

    Harness-authored entries are frozen (digest over checks + budgets). The
    symbol sweep is always present in the AGENT-side suite; the public test
    suite becomes an acceptance check when a tests directory exists;
    workspace-declared checks (harness-checks.json at the workspace root,
    owner/fixture-authored) are imported verbatim so fixtures and real repos
    can add differential and property checks over their own data.

    include_symbol_sweep=False builds the arm-neutral BEHAVIORAL suite the
    campaign runner feeds back to loop arms: the sweep needs the scaffold's
    evidence ledger to record inspections, which a bare arm does not have, so
    it stays a gate control rather than loop feedback.
    """
    checks: list[dict] = []
    if include_symbol_sweep:
        checks.append({"id": "symbol-sweep", "kind": "symbol-sweep", "authored_by": "harness"})
    if (workspace / "tests").is_dir():
        checks.append({
            "id": "public-tests",
            "kind": "acceptance",
            "authored_by": "harness",
            "command": ["python3", "-m", "unittest", "discover", "-s", "tests"],
        })
    # Two declaration sources: a real repo declares its own checks at the
    # workspace root; a benchmark fixture declares them OUTSIDE the public
    # workspace (harness_dir) so the unscaffolded control stays bare. Scripts
    # are materialized into script_home and pinned by sha256 so an agent
    # rewriting a check script fails closed at re-run time.
    declarations: list[tuple[Path, Path | None]] = []
    workspace_declared = workspace / "harness-checks.json"
    if workspace_declared.is_file():
        declarations.append((workspace_declared, workspace))
    if harness_dir is not None and (Path(harness_dir) / "harness-checks.json").is_file():
        declarations.append((Path(harness_dir) / "harness-checks.json", Path(harness_dir)))
    if script_home is None:
        script_home = workspace / ".agentic" / "harness-checks"
    script_home = Path(script_home)
    for declared, home in declarations:
        for row in json.loads(declared.read_text(encoding="utf-8-sig")).get("checks", []):
            row = dict(row)
            row["authored_by"] = "harness"
            script_name = row.pop("script", None)
            if script_name:
                source = (home / "checks" / script_name) if home is not None else None
                if source is None or not source.is_file():
                    raise RuntimeError(f"declared check script not found: {script_name}")
                script_home.mkdir(parents=True, exist_ok=True)
                target = script_home / script_name
                shutil.copyfile(source, target)
                try:
                    command_path = target.resolve().relative_to(workspace.resolve()).as_posix()
                except ValueError:
                    command_path = str(target.resolve())
                row["command"] = ["python3", command_path]
                row["files"] = [{"path": command_path, "sha256": digest(target)}]
            checks.append(row)
    if spec_first:
        # Spec acceptance tests are agent-authored during spec synthesis and
        # re-executed by the gate's spec-first controls; the suite carries a
        # pointer check so the loop fails until the spec is validated+frozen.
        checks.append({
            "id": "spec-frozen",
            "kind": "acceptance",
            "authored_by": "harness",
            "command": ["python3", "-c",
                        "import pathlib,sys; sys.exit(0 if pathlib.Path('.agentic/spec-freeze.json').is_file() else 1)"],
        })
    suite = {"schema_version": 1, "config": {"max_iterations": 5, "no_progress_limit": 2}, "checks": checks}
    suite["harness_freeze_sha256"] = harness_freeze_sha256(suite)
    return suite


def prepare(task_path: Path, workspace: Path, output: Path, changed_paths: list[str], forced_mode: str | None = None,
            harness_dir: Path | None = None) -> dict:
    task = task_path.read_text(encoding="utf-8-sig")
    ledger = compile_ledger(task, str(task_path))
    decision = route(task, changed_paths, forced_mode)
    if not forced_mode and decision["mode"] == "lite" and not decision["analysis"].get("advisory"):
        # Compiled scope beyond the trivial boundary escalates lite to standard
        # before any mutation. This is the only scope-based escalation left.
        modes_path = HERE / "modes.json"
        if not modes_path.exists():
            modes_path = REPO / "Runtime/adaptive-modes.json"
        policy = json.loads(modes_path.read_text(encoding="utf-8-sig"))
        boundary = next(m for m in policy["modes"] if m["id"] == "lite").get("trivial_boundary", {})
        if (len(ledger["requirements"]) > boundary.get("max_requirements", 4)
                or len(changed_paths) > boundary.get("max_changed_files", 2)):
            decision = route(task, changed_paths, minimum_mode="standard")
    output.mkdir(parents=True, exist_ok=True)
    dump(output / "mode-decision.json", decision)
    findings_section = decision.get("relevant_findings") or {}
    if findings_section.get("findings"):
        dump(output / "relevant-findings.json", findings_section)
    if decision["analysis"].get("advisory") and not forced_mode:
        (output / "agent_prompt_appendix.txt").write_text(
            "Advisory read-only mode selected. Do not mutate files; answer with sources.\n", encoding="utf-8")
        return {"mode": decision["mode"], "advisory": True, "context_characters": 0, "requirements": 0, "modules": []}

    capabilities = set(decision["capabilities"])
    loop_enabled = "verification-loop" in capabilities
    spec_first = "spec-synthesis" in capabilities
    continuity = "durable-checkpoints" in capabilities or "session-handoff-state" in capabilities

    agent_ledger = compact_ledger(ledger) if "compact-requirement-ledger" in capabilities else ledger
    dump(output / "objective-ledger.json", agent_ledger)
    shutil.copyfile(REPO / "Core/runtime.md", output / "core.md")
    evidence = {
        "schema_version": 3,
        "mode": decision["mode"],
        "capabilities": decision["capabilities"],
        "requirements": [{"requirement_id": row["id"], "status": "pending", "reason": None, "evidence": []} for row in ledger["requirements"]],
        "ambiguity_resolutions": [],
        "verification_runs": [],
        "consumer_inspections": [],
        "scope_approval": {"status": "not-required", "approved_by": None, "scope": None},
        "independent_verification": {"status": "not-required", "verifier_profile": None, "evidence": []},
        "completion_claim": {"status": "in_progress", "summary": None}
    }

    if continuity:
        dump(output / "checkpoint.json", {
            "schema_version": 1, "required": True, "status": "pending",
            "objective_id": ledger["task_sha256"], "completed_requirements": [],
            "evidence_refs": [], "decisions": [], "blockers": [], "next_action": None,
        })
        dump(output / "session-handoff.json", {
            "schema_version": 1, "required": True, "status": "pending",
            "resume_from": None, "verified_state": [], "pending_requirements": [row["id"] for row in ledger["requirements"]],
            "next_action": None, "forbidden_assumptions": [],
        })

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

    suite = None
    if loop_enabled:
        # The forcing functions: snapshot the pre-change workspace, freeze the
        # independent check suite, and ship the loop tooling beside the gate.
        record = snapshot_baseline(workspace, output / "baseline-workspace")
        dump(output / "baseline-record.json", record)
        suite = compile_check_suite(workspace, spec_first, harness_dir=harness_dir,
                                    script_home=output / "harness-checks")
        dump(output / "check-suite.json", suite)
        shutil.copyfile(HERE / "harness_checks.py", output / "harness_checks.py")
        shutil.copyfile(HERE / "verification_loop.py", output / "verification_loop.py")

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
    if loop_enabled:
        completion_requires += [
            "verification loop green: the gate re-runs the frozen independent check suite itself",
            "check suite integrity intact: harness-authored checks and budgets unmodified",
        ]
    if continuity:
        completion_requires += ["durable checkpoint ready", "session handoff ready"]
    if spec_first:
        completion_requires += [
            "spec validated (spec_synthesis validate PASS) and freeze recorded in spec-freeze.json",
            "ledger freeze intact: no frozen requirement removed, rewritten or downgraded without an owner_scope_change entry",
            "every spec acceptance test re-executed by the gate and passing",
        ]
    enforcement = {
        "schema_version": 3,
        "mode": decision["mode"],
        "hard_gate": True,
        "completion_commands": {"windows": "powershell -ExecutionPolicy Bypass -File .agentic/run-pre-submit.ps1", "posix": "bash .agentic/run-pre-submit.sh"},
        "completion_requires": completion_requires,
        "host_hidden_grader_is_not_agent_completion_evidence": True,
        "check_suite_freeze_sha256": suite["harness_freeze_sha256"] if suite else None,
        "independent_verifier_required": "independent-verifier" in capabilities,
        "human_gate": decision["model_routing"]["human_gate"]
    }
    if "human-approval-boundaries" in capabilities:
        evidence["scope_approval"] = {"status": "pending", "approved_by": None, "scope": None}
    if "independent-verifier" in capabilities:
        evidence["independent_verification"] = {
            "status": "pending",
            "verifier_profile": decision["model_routing"]["verifier_profile"],
            "evidence": []
        }
    dump(output / "evidence.json", evidence)
    dump(output / "enforcement.json", enforcement)
    dump(output / "context-manifest.json", {"schema_version": 4, "mode": decision["mode"], "core": "core.md", "ledger_profile": agent_ledger.get("ledger_profile", "full"), "modules": copied, "context_characters": context_characters, "context_budget": decision["context_budget"], "requirement_count": len(ledger["requirements"]), "loop_enabled": loop_enabled, "checkpoint_required": continuity, "spec_first": spec_first})
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
        + ("VERIFICATION LOOP: your work is checked by an independent, frozen check suite, not by your claims. After implementing, run "
           "`python .agentic/verification_loop.py step --suite .agentic/check-suite.json --workspace .` and read .agentic/loop-feedback.json. "
           "Exit 0: proceed to the gate. Exit 1: fix the listed failures at their cause and step again. Exit 2: stop and escalate with the failures. "
           "Never weaken, remove or reconfigure checks (the suite is digest-frozen; the gate re-runs it independently). "
           "A consumer file flagged by the symbol sweep must be either updated or recorded in evidence.json consumer_inspections with a note after you actually read it. "
           if loop_enabled else "")
        + ("Before a session boundary, make .agentic/checkpoint.json and .agentic/session-handoff.json ready and evidence-backed. " if continuity else "")
        + "Before claiming completion, run the platform command in .agentic/enforcement.json; a FAIL blocks completion. "
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
    parser.add_argument("--force-mode", choices=["lite", "standard", "critical"])
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    task_path = args.task_file if args.task_file.is_absolute() else workspace / args.task_file
    output = args.output_dir or workspace / ".agentic"
    print(json.dumps(prepare(task_path.resolve(), workspace, output.resolve(), args.changed_path, args.force_mode), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
