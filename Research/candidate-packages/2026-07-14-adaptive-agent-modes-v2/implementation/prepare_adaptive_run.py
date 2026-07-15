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
from fixture_admission import local_fixture_dir, resolve_command
from prepare_context import prepare

HERE = Path(__file__).resolve().parent


def repo_root() -> Path:
    for parent in (HERE, *HERE.parents):
        if (parent / "Runtime/stable/manifest.json").exists():
            return parent
    raise RuntimeError("AgenticWorkBestPractices root not found")


REPO = repo_root()
CANDIDATE = HERE.parent
ARMS = ["vanilla", "mode-1-lean", "mode-2-routed", "mode-3-assured", "full"]


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
    shutil.copytree(public, workspace)
    task = workspace / "task.md"
    context = workspace / ".agentic"
    task_text = task.read_text(encoding="utf-8-sig")
    if args.arm == "vanilla":
        # The runtime Vanilla mode is intentionally read-only. A coding benchmark
        # control must instead be genuinely unscaffolded: task only, no Candidate
        # context directory, no completion gate and no instruction prohibiting edits.
        policy_decision = route(task_text)
        prepared = {"mode":"vanilla-control","context_characters":0,"requirements":0,"modules":[]}
        prompt = task_text.rstrip() + "\n"
        policy_selected_mode = policy_decision["policy_selected_mode"]
        agent_context_files: list[str] = []
    else:
        prepared = prepare(task, workspace, context, [], args.arm)
        policy_selected_mode = json.loads((context / "mode-decision.json").read_text(encoding="utf-8"))["policy_selected_mode"]
        agent_context_files = [path.relative_to(workspace).as_posix() for path in context.rglob("*") if path.is_file()]
        appendix = (context / "agent_prompt_appendix.txt").read_text(encoding="utf-8-sig")
        prompt = task_text.rstrip() + "\n\n---\n" + appendix
    if args.arm == "full" and args.approved_by:
        evidence_path = context / "evidence.json"
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        evidence["scope_approval"] = {"status":"approved","approved_by":args.approved_by,"scope":"approved six-call scaffolding ablation only"}
        evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.arm == "full":
        prompt += ("This is the primary Full pass. Complete and evidence every primary requirement, set completion_claim.status to ready, and record the existing human scope approval. "
                   "Never fabricate independent verification. The pre-submit gate may remain blocked only by independent-verification until the separate fresh verifier call runs; all other failures remain your responsibility.\n")
    (args.output / "prompt.txt").write_text(prompt, encoding="utf-8")
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
        "completion_gate": None if args.arm == "vanilla" else ".agentic/enforcement.json",
        "hidden_grader_copied": False,
    }
    (args.output / "run-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
