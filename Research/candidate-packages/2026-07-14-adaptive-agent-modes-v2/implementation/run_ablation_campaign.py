#!/usr/bin/env python3
"""Sequential, approval-locked campaign runner with verification-loop arms.

Loop arms ("<context>-loop") implement the iteration experiment: after each
provider call the HOST runs the independent check suite (host-side copy, never
the agent-writable one); failures are returned verbatim as structured feedback
in a fresh follow-up call whose workspace continues from the previous
iteration. Termination per trial is hard: green, iteration ceiling, identical
failure fingerprint (no-progress), or campaign call budget. Every iteration is
a provider call and counts toward the approved ceiling.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import author_role
import check_authoring
import harness_checks
import notes_bank
from fixture_admission import local_fixture_dir
from prepare_context import compile_check_suite


def repo_root() -> Path:
    for parent in HERE.parents:
        if (parent / "Runtime/stable/manifest.json").exists():
            return parent
    raise RuntimeError("repository root not found")


REPO = repo_root()


def save(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def call(command: list[str], timeout: int = 2400) -> int:
    completed = subprocess.run(command, cwd=REPO, timeout=timeout)
    return completed.returncode


def invoke_provider(run_id: str, campaign: dict) -> int:
    provider = campaign["provider_snapshot"]["provider"]
    return call([
        "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(REPO / "Evals/adapters/providers/invoke-agenticbench.ps1"),
        "-Run", run_id, "-Provider", provider["id"], "-Model", provider["model"], "-Effort", provider["effort"],
        "-MaxTurns", str(campaign["loop"]["max_turns_per_call"]), "-MaxWallMinutes", str(campaign["loop"]["max_wall_minutes_per_call"]), "-Execute"
    ])


def count_provider_call(campaign: dict, run: Path, exit_code: int) -> None:
    """Honest spend accounting: an adapter refusal BEFORE the provider was
    invoked (no provider-execution.json) consumed nothing and is not counted
    against the approved ceiling; every genuine invocation is."""
    if exit_code != 0 and not (run / "provider-execution.json").is_file():
        campaign.setdefault("uncounted_adapter_refusals", []).append(run.name)
        return
    campaign["provider_calls"] += 1


def prepare_solution(campaign: dict, entry: dict) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S%f")[:-3]
    run_id = f"{stamp}-{campaign['fixture']}-{entry['arm']}-t{entry.get('trial', 1)}"
    run = REPO / "Evals/runs" / run_id
    context_arm = entry.get("context_arm") or entry["arm"]
    command = [sys.executable, str(HERE / "prepare_adaptive_run.py"), "--fixture", campaign["fixture"], "--arm", context_arm, "--output", str(run), "--provider", campaign["provider_snapshot"]["provider"]["id"], "--trial", str(entry.get("trial", 1))]
    if context_arm == "critical":
        command += ["--approved-by", campaign["approval"]["approved_by"]]
    if call(command, 120) != 0:
        raise RuntimeError("solution preparation failed")
    if entry["arm"] != context_arm:
        # The campaign arm (e.g. standard-loop) is the analysis unit; the
        # context arm names what the agent actually received.
        manifest_path = run / "run-manifest.json"
        manifest = load(manifest_path)
        manifest["arm"] = entry["arm"]
        manifest["context_arm"] = context_arm
        save(manifest_path, manifest)
    entry["run_id"] = run_id
    entry["status"] = "prepared"
    return run


def host_loop_setup(run: Path, fixture: str) -> None:
    """Host-side, agent-unreachable copy of the check suite and baseline.

    The workspace copy of the suite (scaffolded arms) is for the AGENT's loop;
    grading and feedback always use this host copy - scripts live in the run
    dir (outside the workspace) with absolute command paths, so a tampering
    agent cannot influence its own feedback or the iteration verdicts.
    """
    workspace = run / "workspace"
    record = harness_checks.snapshot_baseline(workspace, run / "host-baseline")
    (run / "host-baseline-record.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fixture_dir, local_contract = local_fixture_dir(fixture)
    harness_dir = fixture_dir / "harness" if (local_contract is not None and (fixture_dir / "harness").is_dir()) else None
    # Behavioral checks only: identical feedback for bare and scaffolded loop
    # arms (the symbol sweep needs the scaffold's evidence ledger).
    suite = compile_check_suite(workspace, spec_first=False, include_symbol_sweep=False,
                                harness_dir=harness_dir, script_home=run / "host-checks")
    save(run / "host-check-suite.json", suite)


def author_host_suite(campaign: dict, campaign_path: Path, base_run: Path, entry: dict,
                      executed: int, max_calls: int) -> int:
    """Spend up to one call per round on a clean-context author, admit, merge.

    Returns the calls spent here. Raises AuthoringShortfall when nothing
    behavioural survives admission: the trial must not run without the mechanism
    it exists to measure.
    """
    workspace = base_run / "workspace"
    # The authoring/admission baseline is the PRISTINE WORKSPACE, not the
    # host-baseline snapshot: the snapshot strips node_modules (and every
    # excluded dir), which starves authored checks of the code's own runtime at
    # admission -- every check error-reds on import and the arm is refused for a
    # reason that is the harness's fault (observed live 2026-07-19). Pristineness
    # is verified, not assumed: authoring runs before any solution call, and
    # this check makes that ordering a fact rather than a convention.
    author_role.verify_pristine(workspace, load(base_run / "host-baseline-record.json"))
    baseline = workspace
    detected = author_role.detect_project(workspace)
    task_text = (workspace / "task.md").read_text(encoding="utf-8-sig")
    # Institutional notes: lessons from errors PRIOR agents made here, routed by
    # the fixture's declared domain tags. Which notes were injected is recorded
    # per run, because a transfer measurement without attribution is an anecdote.
    _, contract = local_fixture_dir(campaign["fixture"])
    tags = set((contract or {}).get("context_tags") or []) or None
    notes = notes_bank.relevant_notes(notes_bank.load_bank(), "check-author", tags)
    brief = author_role.build_brief(base_run, task_text, detected, notes=notes)
    save(base_run / "author-notes.json",
         {"injected_note_ids": [note["id"] for note in notes], "context_tags": sorted(tags or [])})
    save(base_run / "author-detected-project.json", detected)
    (base_run / "author-brief.txt").write_text(brief, encoding="utf-8")

    ceiling = int(campaign["loop"]["authoring"]["max_calls_per_trial"])
    spent = {"calls": 0}

    def responder(prompt: str) -> str:
        # Every author round is a real, counted provider call. The budget is
        # checked HERE rather than by the caller, because check_authoring's
        # re-author round would otherwise spend a call nobody approved.
        if spent["calls"] >= ceiling:
            raise check_authoring.AuthoringError("author call ceiling for this trial is exhausted")
        if executed + spent["calls"] >= max_calls or campaign["provider_calls"] >= campaign["loop"]["max_total_provider_calls"]:
            raise check_authoring.AuthoringError("campaign call budget exhausted before authoring completed")
        round_index = spent["calls"] + 1
        run_id = f"{base_run.name}-author{round_index}"
        author_run = author_role.prepare_author_run(
            REPO / "Evals/runs", run_id, baseline, prompt,
            campaign["provider_snapshot"]["provider"]["id"])
        code = invoke_provider(run_id, campaign)
        campaign["provider_calls"] += 1
        spent["calls"] += 1
        entry.setdefault("author_runs", []).append({"run_id": run_id, "exit_code": code})
        save(campaign_path, campaign)
        if code != 0:
            raise check_authoring.AuthoringError(f"the author's provider call exited {code}")
        return author_role.collect_proposal(author_run)

    suite = load(base_run / "host-check-suite.json")
    try:
        merged, record = author_role.author_into(
            suite, responder, brief, baseline, base_run / "author-scratch", detected,
            max_calls=ceiling)
    finally:
        save(base_run / "author-record.json", {"calls": spent["calls"]})
    save(base_run / "host-check-suite.json", merged)
    save(base_run / "author-result.json",
         {k: v for k, v in record.items() if k != "files"})
    # The admitted scripts must exist in the workspace the agent works in, and in
    # every iteration copied from it, or the pinned command finds no file and the
    # check fails closed for a reason the agent did not cause.
    author_role.install_checks(record["files"], workspace)
    entry["authored_checks"] = [check["id"] for check in author_role.behavioural(record["checks"])]
    return spent["calls"]


def derived_suite_setup(campaign: dict, base_run: Path, entry: dict) -> bool:
    """Install a mechanically derived frozen suite for this arm, if declared.

    Host-side ONLY: the derived check (kind `derived`, sha-pinned pins/corpus)
    goes into the run dir's host-check-suite.json, never into the agent's
    workspace — the pins hold oracle-grade expectations, and an agent that can
    read them can satisfy them by lookup instead of by work. The agent sees
    exactly what every loop arm sees: structured failures as feedback.
    Returns True when this arm runs on a derived suite (no authoring).
    """
    spec = (campaign["loop"].get("derived_suites") or {}).get(entry["arm"])
    if not spec:
        return False
    pins = (REPO / spec["pins"]).resolve()
    check = {
        "id": spec.get("id", f"derived-{spec['layer']}"),
        "kind": "derived",
        "authored_by": "harness",
        "layer": spec["layer"],
        "pins": str(pins),
        "files": [{"path": str(pins), "sha256": harness_checks.sha256_bytes(pins)}],
    }
    if spec.get("corpus"):
        corpus = (REPO / spec["corpus"]).resolve()
        check["corpus"] = str(corpus)
        check["files"].append({"path": str(corpus), "sha256": harness_checks.sha256_bytes(corpus)})
    suite = load(base_run / "host-check-suite.json")
    suite.setdefault("checks", []).append(check)
    suite["harness_freeze_sha256"] = harness_checks.harness_freeze_sha256(suite)
    save(base_run / "host-check-suite.json", suite)
    entry["derived_suite"] = check["id"]
    return True


def host_run_checks(base_run: Path, current_run: Path, iteration: int) -> dict:
    suite = load(base_run / "host-check-suite.json")
    record = load(base_run / "host-baseline-record.json")
    workspace = current_run / "workspace"
    evidence_path = workspace / ".agentic/evidence.json"
    evidence = load(evidence_path) if evidence_path.is_file() else None
    report = harness_checks.run_suite(suite, workspace, evidence=evidence,
                                      baseline_record=record, baseline_dir=base_run / "host-baseline")
    save(current_run / f"host-loop-report-i{iteration}.json", report)
    return report


def prepare_iteration(campaign: dict, entry: dict, previous_run: Path, report: dict, iteration: int) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S%f")[:-3]
    run_id = f"{stamp}-{campaign['fixture']}-{entry['arm']}-t{entry.get('trial', 1)}-i{iteration}"
    run = REPO / "Evals/runs" / run_id
    run.mkdir(parents=True)
    shutil.copytree(previous_run / "workspace", run / "workspace")
    failures = [
        {"check_id": row["id"], "kind": row["kind"], "failures": row["failures"],
         **({"guidance": row["guidance"]} if row.get("guidance") else {})}
        for row in report["checks"] if row["verdict"] != "PASS"
    ]
    base_prompt = (previous_run / "prompt.txt").read_text(encoding="utf-8-sig")
    marker = "\n\n--- INDEPENDENT CHECK FEEDBACK"
    original_prompt = base_prompt.split(marker)[0]
    prompt = (original_prompt.rstrip()
              + f"{marker} (iteration {iteration}) ---\n"
              + "Your previous attempt is in this workspace. An independent harness ran its own checks against your work; "
              + "the failures below are real and must be fixed at their cause. Do not weaken, remove or reconfigure any check.\n"
              + json.dumps({"failures": failures}, ensure_ascii=False, indent=2) + "\n")
    (run / "prompt.txt").write_text(prompt, encoding="utf-8")
    manifest = load(previous_run / "run-manifest.json")
    manifest.update({
        "run_id": run_id,
        "iteration": iteration,
        "parent_run": previous_run.name,
        "prompt_sha256": harness_checks.sha256_bytes(run / "prompt.txt"),
        "prepared_at": datetime.now(timezone.utc).isoformat(),
    })
    save(run / "run-manifest.json", manifest)
    return run


def grade(run: Path) -> int:
    return call([sys.executable, str(HERE / "grade_adaptive_run.py"), "--run", str(run), "--repo", str(REPO)], 180)


def classify_grading_failure(run: Path) -> str:
    """Agent violations are DATA, infrastructure failures are fatal.

    A run-record that exists but is outcome-invalid because the agent touched
    protected files is a valid negative observation (the guardrail worked):
    record it and continue the campaign. Anything else (no record, grader
    crash, invalid score shape) stops the campaign fail-closed as before.
    """
    record_path = run / "run-record.json"
    if record_path.is_file():
        record = load(record_path)
        if record.get("protected_files_changed"):
            return "graded-invalid-protected-violation"
    return "infrastructure"


def run_loop_arm(campaign: dict, campaign_path: Path, entry: dict, executed: int, max_calls: int) -> tuple[int, bool]:
    """Run one loop-arm trial. Returns (calls_executed_here, campaign_should_stop)."""
    base_run = prepare_solution(campaign, entry)
    host_loop_setup(base_run, campaign["fixture"])
    save(campaign_path, campaign)
    calls_here = 0
    derived = derived_suite_setup(campaign, base_run, entry)
    if not derived and campaign["loop"].get("authoring", {}).get("enabled"):
        try:
            calls_here += author_host_suite(campaign, campaign_path, base_run, entry,
                                            executed, max_calls)
        except author_role.AuthoringShortfall as error:
            # NOT a bad score: a trial that never held the mechanism. Recording
            # it as a result would publish a number about vanilla-plus-nothing
            # and label it the loop. Stop and say so.
            entry["status"] = "arm-invalid-no-admitted-checks"
            entry["arm_invalid_reason"] = str(error)
            campaign["status"] = "stopped-arm-carries-no-mechanism"
            save(campaign_path, campaign)
            return calls_here, True
        save(campaign_path, campaign)
    current = base_run
    fingerprints: list[str] = []
    for iteration in range(1, int(entry.get("max_iterations", 1)) + 1):
        if (REPO / campaign["loop"]["kill_switch"]).exists():
            campaign["status"] = "stopped-by-kill-switch"
            return calls_here, True
        if executed + calls_here >= max_calls or campaign["provider_calls"] >= campaign["loop"]["max_total_provider_calls"]:
            entry["loop_outcome"] = "call-budget-exhausted"
            break
        code = invoke_provider(current.name, campaign)
        campaign["provider_calls"] += 1
        calls_here += 1
        save(campaign_path, campaign)
        if code != 0:
            entry["status"] = "provider-failed"
            campaign["status"] = "stopped-after-provider-failure"
            return calls_here, True
        report = host_run_checks(base_run, current, iteration)
        entry["iterations"].append({
            "iteration": iteration,
            "run_id": current.name,
            "green": report["green"],
            "failing_check_ids": report["failing_check_ids"],
            "failure_fingerprint": report["failure_fingerprint"],
        })
        entry["run_id"] = current.name
        if report["green"]:
            entry["loop_outcome"] = "green"
            break
        if fingerprints and fingerprints[-1] == report["failure_fingerprint"]:
            entry["loop_outcome"] = "no-progress"
            break
        fingerprints.append(report["failure_fingerprint"])
        if iteration == int(entry.get("max_iterations", 1)):
            entry["loop_outcome"] = "iteration-budget"
            break
        current = prepare_iteration(campaign, entry, current, report, iteration + 1)
        save(campaign_path, campaign)
    entry.setdefault("loop_outcome", "call-budget-exhausted")
    final_run = REPO / "Evals/runs" / entry["run_id"]
    graded = grade(final_run)
    if graded == 0:
        entry["status"] = "graded"
        return calls_here, False
    verdict = classify_grading_failure(final_run)
    if verdict != "infrastructure":
        entry["status"] = verdict
        return calls_here, False
    entry["status"] = "grading-failed"
    campaign["status"] = "stopped-after-grading-failure"
    return calls_here, True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--max-calls", type=int, default=1)
    args = parser.parse_args()
    campaign_path = args.campaign.resolve()
    campaign = load(campaign_path)
    if campaign["status"] not in ("approved", "running") or not campaign["approval"].get("approved_by"):
        raise SystemExit("campaign requires exact human approval")
    if args.max_calls < 1 or args.max_calls > campaign["loop"]["max_calls_per_invocation"]:
        raise SystemExit("invalid invocation call ceiling")
    if datetime.now(timezone.utc) >= datetime.fromisoformat(campaign["provider_snapshot"]["expires_at"]):
        raise SystemExit("provider snapshot expired")
    if (REPO / campaign["loop"]["kill_switch"]).exists():
        raise SystemExit("kill switch active")
    lock_path = campaign_path.with_suffix(".runner.lock")
    # The provider adapter is a global mutex: two campaign runners can never
    # overlap, whatever campaign they serve. Refuse to start while ANY runner
    # lock exists (learned live 2026-07-16: a resumed runner survived a kill
    # switch that was cleared too early and collided with the next campaign).
    other_locks = [p for p in campaign_path.parent.glob("*.runner.lock") if p != lock_path]
    if other_locks:
        raise SystemExit(f"another campaign runner is active: {other_locks[0].name}")
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise SystemExit("campaign runner lock exists")
    executed = 0
    try:
        campaign["status"] = "running"
        save(campaign_path, campaign)
        while executed < args.max_calls and campaign["provider_calls"] < campaign["loop"]["max_total_provider_calls"]:
            if (REPO / campaign["loop"]["kill_switch"]).exists():
                campaign["status"] = "stopped-by-kill-switch"
                break
            entry = next((row for row in campaign["runs"] if row["status"] == "pending"), None)
            if not entry:
                break
            if entry.get("loop"):
                calls_here, stop = run_loop_arm(campaign, campaign_path, entry, executed, args.max_calls)
                executed += calls_here
                save(campaign_path, campaign)
                if stop:
                    break
            else:
                run = prepare_solution(campaign, entry)
                save(campaign_path, campaign)
                code = invoke_provider(run.name, campaign)
                campaign["provider_calls"] += 1; executed += 1
                entry["status"] = "provider-complete" if code == 0 else "provider-failed"
                if code != 0:
                    campaign["status"] = "stopped-after-provider-failure"; break
                graded = grade(run)
                if graded == 0:
                    entry["status"] = "graded"
                else:
                    verdict = classify_grading_failure(run)
                    entry["status"] = verdict if verdict != "infrastructure" else "grading-failed"
                    if verdict == "infrastructure":
                        campaign["status"] = "stopped-after-grading-failure"; break
            save(campaign_path, campaign)
        all_solutions = all(row["status"] in ("graded", "graded-invalid-protected-violation") for row in campaign["runs"])
        verifier_done = (not campaign.get("independent_verifier_runs")
                         or campaign["independent_verifier_runs"][0]["status"] in ("complete", "complete-quality-failure"))
        if all_solutions and verifier_done and campaign["provider_calls"] <= campaign["loop"]["max_total_provider_calls"]:
            campaign["status"] = "complete"
        save(campaign_path, campaign)
        print(json.dumps({"campaign_id":campaign["campaign_id"],"executed_this_invocation":executed,"provider_calls_total":campaign["provider_calls"],"status":campaign["status"]},indent=2))
    finally:
        os.close(fd)
        lock_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
