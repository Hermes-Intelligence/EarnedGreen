#!/usr/bin/env python3
"""Prepare a clean, zero-provider benchmark workspace for one adaptive mode arm."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from adaptive_router import route
from fixture_admission import Gate, local_fixture_dir, resolve_command
from prepare_context import prepare

HERE = Path(__file__).resolve().parent


def repo_root() -> Path:
    for parent in (HERE, *HERE.parents):
        if (parent / "Runtime/stable/manifest.json").exists():
            return parent
    raise RuntimeError("AgenticWorkBestPractices root not found")


REPO = repo_root()
CANDIDATE = HERE.parent
# "vanilla" is the unscaffolded benchmark CONTROL (task only), not a runtime
# mode. Runtime modes are lite/standard/critical (modes.json schema 4).
ARMS = ["vanilla", "vanilla-configured", "lite", "standard", "critical"]

# What a competent engineer sets up WITHOUT this environment: repo instructions
# that point at the house conventions and demand the tests are run before "done".
# This is the arm that decides whether the environment is worth anything. If the
# loop cannot beat a well-configured vanilla, the honest conclusion is that the
# value was "someone wrote good checks", not our machinery -- and we say so.
#
# It is deliberately STRONG: it gets the conventions and an explicit iterate-to-
# green instruction (what a test hook enforces in real life). What it does NOT
# get is the only thing under test: harness-EXECUTED frozen checks that the agent
# cannot edit, and a gate that re-runs them itself instead of asking.
VANILLA_CONFIGURED_AGENTS_MD = """\
# Repository instructions

Read `CONVENTIONS.md` before changing anything. It documents the house rules this
code is held to, and it is the standard your work will be judged against.

Before you report the task as done:

* run the tests: `{test_command}`
* they must pass. If they do not, fix the cause and run them again.
* never weaken, skip or delete a test to make the suite pass.
* check your change against every rule in `CONVENTIONS.md`, not just the ones the
  tests happen to cover.

Do not report the work as complete until the tests are green and the conventions
are satisfied.
"""


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def relative_inventory(workspace: Path) -> list[dict[str, str]]:
    rows = []
    for path in sorted(item for item in workspace.rglob("*") if item.is_file() and ".agentic" not in item.parts):
        rows.append({"path": path.relative_to(workspace).as_posix(), "sha256": sha(path)})
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--arm", choices=ARMS, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--provider", default="manual")
    parser.add_argument("--trial", type=int, default=1)
    parser.add_argument("--approved-by")
    args = parser.parse_args()
    candidate_fixture, local_contract = local_fixture_dir(args.fixture)
    if local_contract is not None:
        public = candidate_fixture / "public"
        fixture_def = {
            "task_file":"task.md",
            "hidden_grader":(candidate_fixture / local_contract["hidden_grader"]).relative_to(REPO).as_posix(),
            "public_test":local_contract["public_test"],
        }
    else:
        public = REPO / "Evals" / "fixtures" / args.fixture / "public"
        catalog = json.loads((REPO / "Evals/fixtures/catalog.json").read_text(encoding="utf-8-sig"))
        fixture_def = next((row for row in catalog["fixtures"] if row["id"] == args.fixture), None)
    if not public.exists():
        raise SystemExit(f"unknown fixture: {args.fixture}")
    if fixture_def is None:
        raise SystemExit(f"unknown fixture: {args.fixture}")
    if args.output.exists() and any(args.output.iterdir()):
        raise SystemExit("output must be absent or empty")
    workspace = args.output / "workspace"
    if local_contract is not None:
        # Candidate-local fixtures provision through the admission Gate: for
        # proprietary fixtures this materializes the real parser from the local
        # Hermes git ref (base = before-state). A plain public copy would hand
        # the agent a workspace with no code to rework.
        workspace.mkdir(parents=True)
        Gate(candidate_fixture)._provision(workspace, [])
    else:
        shutil.copytree(public, workspace)
    task = workspace / "task.md"
    context = workspace / ".agentic"
    task_text = task.read_text(encoding="utf-8-sig")
    if args.arm in ("vanilla", "vanilla-configured"):
        # The runtime Vanilla mode is intentionally read-only. A coding benchmark
        # control must instead be genuinely unscaffolded: task only, no Candidate
        # context directory, no completion gate and no instruction prohibiting edits.
        policy_decision = route(task_text)
        prepared = {"mode":"vanilla-control","context_characters":0,"requirements":0,"modules":[]}
        prompt = task_text.rstrip() + "\n"
        policy_selected_mode = policy_decision["policy_selected_mode"]
        agent_context_files: list[str] = []
        if args.arm == "vanilla-configured":
            # Repo instructions, as a real team would leave them. Written into the
            # workspace AND inlined into the prompt: whether a given adapter
            # auto-loads AGENTS.md is an accident of tooling, and an arm that
            # silently never saw its own configuration would be a strawman.
            agents_md = VANILLA_CONFIGURED_AGENTS_MD.format(
                test_command=" ".join(fixture_def["public_test"]))
            (workspace / "AGENTS.md").write_text(agents_md, encoding="utf-8")
            (workspace / "CLAUDE.md").write_text(agents_md, encoding="utf-8")
            prompt = task_text.rstrip() + "\n\n---\n" + agents_md
            agent_context_files = ["AGENTS.md", "CLAUDE.md"]
            prepared = {"mode": "vanilla-configured-control",
                        "context_characters": len(agents_md), "requirements": 0, "modules": []}
    else:
        harness_dir = candidate_fixture / "harness" if (local_contract is not None and (candidate_fixture / "harness").is_dir()) else None
        prepared = prepare(task, workspace, context, [], args.arm, harness_dir=harness_dir)
        policy_selected_mode = json.loads((context / "mode-decision.json").read_text(encoding="utf-8"))["policy_selected_mode"]
        agent_context_files = [path.relative_to(workspace).as_posix() for path in context.rglob("*") if path.is_file()]
        appendix = (context / "agent_prompt_appendix.txt").read_text(encoding="utf-8-sig")
        prompt = task_text.rstrip() + "\n\n---\n" + appendix
    if args.arm == "critical" and args.approved_by:
        evidence_path = context / "evidence.json"
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        evidence["scope_approval"] = {"status":"approved","approved_by":args.approved_by,"scope":"approved scaffolding-ablation campaign only"}
        evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.arm == "critical":
        prompt += ("This is the primary Critical pass. Complete and evidence every primary requirement, set completion_claim.status to ready, and record the existing human scope approval. "
                   "Never fabricate independent verification. The pre-submit gate may remain blocked only by independent-verification until the separate fresh verifier call runs; all other failures remain your responsibility.\n")
    (args.output / "prompt.txt").write_text(prompt, encoding="utf-8")
    # Host-held tamper anchor: the suite freeze digest lives in this manifest
    # OUTSIDE the workspace, so an agent rewriting both the suite and its
    # embedded digest is still caught at grade time.
    check_suite_freeze = None
    if args.arm not in ("vanilla", "vanilla-configured"):
        enforcement_path = context / "enforcement.json"
        if enforcement_path.is_file():
            check_suite_freeze = json.loads(enforcement_path.read_text(encoding="utf-8-sig")).get("check_suite_freeze_sha256")
    initial = relative_inventory(workspace)
    protected_names = {fixture_def["task_file"]} | {row["path"] for row in initial if row["path"].startswith("tests/")}
    manifest = {
        "schema_version": 2,
        "status": "prepared-zero-provider",
        "fixture": args.fixture,
        "arm": args.arm,
        "run_id": args.output.name,
        "provider": args.provider,
        "requested_model_profile": "benchmark-snapshot",
        "actual_model": None,
        "effort": None,
        "trial": args.trial,
        "isolation": "dedicated-wsl",
        "publishable_hidden_result": True,
        "workspace": "workspace",
        "central_hidden_grader": fixture_def["hidden_grader"],
        "public_test": fixture_def["public_test"],
        "public_test_host": resolve_command(list(fixture_def["public_test"]), sys.executable),
        "initial_files": initial,
        "protected_initial_files": [row for row in initial if row["path"] in protected_names],
        "agent_context_files": agent_context_files,
        "policy_selected_mode": policy_selected_mode,
        "forced_for_ablation": True,
        "prepared_at": datetime.now(timezone.utc).isoformat(),
        "provider_calls": 0,
        "task_sha256": sha(task),
        "prompt_sha256": sha(args.output / "prompt.txt"),
        "context": prepared,
        # No gate for either control arm: the gate is the thing under test, and an
        # arm that quietly received it would not be a control.
        "completion_gate": None if args.arm in ("vanilla", "vanilla-configured") else ".agentic/enforcement.json",
        "check_suite_freeze_sha256": check_suite_freeze,
        "hidden_grader_copied": False,
    }
    (args.output / "run-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
