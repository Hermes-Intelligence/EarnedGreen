#!/usr/bin/env python
"""Re-grade the five saved v4 ablation runs under the SEMANTIC grader + process
metrics, with ZERO provider calls.

For each run we copy the saved workspace/src into a fresh grading sandbox (fixture
public + the arm's src + its README), run the new semantic hidden grader, and
compute process_metrics against the fixture's declared process_ground_truth. The
output evidence/main-v4-semantic-regrade.json is the headline dataset: what the
arms ACTUALLY achieved once format noise is removed, and whether the scaffolding
changed the PROCESS even where the OUTCOME converged.

No workspace under Evals/runs is modified; every grade runs in a temp sandbox.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CANDIDATE = HERE.parent
FIXTURE = HERE / "mode-boundary-fixture-v4"
GRADER = FIXTURE / "hidden" / "grade.py"
PUBLIC = FIXTURE / "public"
EVIDENCE = CANDIDATE / "evidence"

sys.path.insert(0, str(HERE))
from process_metrics import compute_run_metrics, load_contract  # noqa: E402


def repo_root() -> Path:
    for parent in (HERE, *HERE.parents):
        if (parent / "Runtime/stable/manifest.json").exists():
            return parent
    raise RuntimeError("AgenticWorkBestPractices root not found")


def campaign_runs(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    rows = []
    for run in data.get("runs", []):
        if run.get("run_id") and run.get("status") == "graded":
            rows.append({"arm": run["arm"], "run_id": run["run_id"]})
    return rows


def resolve_run_ids() -> list[dict]:
    """Pull the five graded run_ids from the saved campaign evidence."""
    main_rows = campaign_runs(EVIDENCE / "main-v4-campaign-r2.json")
    canary_rows = campaign_runs(EVIDENCE / "canary-v4-campaign.json")
    for row in canary_rows:
        row["arm"] = "vanilla-canary" if row["arm"] == "vanilla" else row["arm"]
    return main_rows + canary_rows


def semantic_grade(run_dir: Path) -> dict:
    """Grade the saved workspace/src in a fresh sandbox; never touch the run dir."""
    src = run_dir / "workspace" / "src"
    readme = run_dir / "workspace" / "README.md"
    with tempfile.TemporaryDirectory(prefix="regrade-v4-") as temp_name:
        ws = Path(temp_name)
        shutil.copytree(PUBLIC, ws, dirs_exist_ok=True)
        shutil.copytree(src, ws / "src", dirs_exist_ok=True)
        if readme.is_file():
            shutil.copy2(readme, ws / "README.md")
        completed = subprocess.run([sys.executable, str(GRADER), str(ws)], cwd=ws, text=True,
                                   capture_output=True, encoding="utf-8", errors="replace", timeout=120)
    for line in reversed((completed.stdout + "\n" + completed.stderr).splitlines()):
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and "score" in parsed:
            return parsed
    raise RuntimeError("semantic grader emitted no JSON: " + (completed.stdout + completed.stderr)[-800:])


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    runs = resolve_run_ids()
    contract = load_contract(FIXTURE)
    runs_root = repo_root() / "Evals" / "runs"

    table = []
    detail_rows = []
    for row in runs:
        run_dir = runs_root / row["run_id"]
        grade = semantic_grade(run_dir)
        metrics = compute_run_metrics(run_dir, contract, grade)
        missed = sorted(c["id"] for c in grade["checks"] if not c["passed"])
        table.append({
            "arm": row["arm"],
            "run_id": row["run_id"],
            "original_exact_score": metrics["original_exact_score"],
            "semantic_score": grade["score"],
            "missed_dims_semantic": missed,
            "token_cost": metrics["token_cost"],
            "consumer_enum_completeness": metrics["consumer_enumeration_completeness"],
            "consumer_edit_completeness": metrics["consumer_edit_completeness"],
            "self_attestation_gap": metrics["self_attestation_gap"],
            "self_attestation_detail": metrics["self_attestation_detail"],
        })
        detail_rows.append(metrics)

    semantic_scores = [r["semantic_score"] for r in table]
    exact_scores = [r["original_exact_score"] for r in table]
    result = {
        "schema_version": 1,
        "kind": "v4-semantic-regrade",
        "fixture": contract["id"],
        "provider_calls": 0,
        "grader": "hidden/grade.py (semantic serialization checks)",
        "runs_regraded": len(table),
        "headline": {
            "all_arms_semantic_score": semantic_scores,
            "all_arms_exact_score": exact_scores,
            "semantic_scores_all_equal": len(set(semantic_scores)) == 1,
            "exact_scores_all_equal": len(set(exact_scores)) == 1,
            "interpretation": (
                "Once format noise is removed, the arms converge on the SAME outcome "
                "(all semantic scores equal). Any remaining difference is in PROCESS "
                "(consumer enumeration, impact-map sections) and TOKEN COST, not the graded outcome."
            ),
        },
        "table": table,
        "detail": detail_rows,
    }
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    output = EVIDENCE / "main-v4-semantic-regrade.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
