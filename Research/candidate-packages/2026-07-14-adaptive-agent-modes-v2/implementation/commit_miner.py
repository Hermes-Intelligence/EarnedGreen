#!/usr/bin/env python3
"""Mine a real repository's history for shadow-replay candidates.

The diff-oracle pipeline needs (before, after) pairs whose behaviour change is
real and observable. Git history of a working product is FULL of them — every
fix commit is a task the team actually did, with the shipped answer attached.
This miner walks a repo READ-ONLY and ranks commits by replay-worthiness:

  * the message says it repairs behaviour (fix / bug / correct / broken ...)
  * the change is FOCUSED (few source files): a 40-file refactor is not a task,
    it is an era; 1-4 files is something one agent could be asked to redo
  * it touches source, not just docs/config/lockfiles
  * it has a parent (an initial commit has no before-state)

The output is a ranked candidate list for a human (or a later session) to pick
the next task family from. DELIBERATELY NOT AUTOMATED FURTHER: turning a mined
commit into an admitted fixture involves judgement (is the task statable
without leaking the answer? is the surface drivable offline?) and its own
admission gate — the two steps that made vextrum an honest fixture.

Read-only by construction: every git invocation here is a query; nothing
checks out, resets or writes. Proprietary source never leaves the local disk —
the candidate list carries paths and messages, not file contents.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

_FIX_WORDS = re.compile(r"\b(fix(es|ed)?|bug|broken|wrong|incorrect|correct(s|ed)?|repair(s|ed)?|"
                        r"regress(ion|ed)?|hotfix|naprawa|poprawka|błąd)\b", re.I)
_SOURCE_SUFFIXES = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".go", ".rs", ".cs", ".sql"}
_NOISE_NAMES = {"package-lock.json", "yarn.lock", "poetry.lock", "uv.lock"}

_LOG_FORMAT = "%H%x1f%P%x1f%ad%x1f%s"
_FIELD = "\x1f"


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(["git", "-C", str(repo), *args],
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=120)
    if completed.returncode != 0:
        raise RuntimeError(f"git {' '.join(args[:2])} failed in {repo}: {completed.stderr[:300]}")
    return completed.stdout


def parse_log(raw: str) -> list[dict[str, Any]]:
    """Parse `git log --format=<_LOG_FORMAT> --numstat` output into commit rows."""
    commits: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in raw.splitlines():
        if _FIELD in line:
            sha, parents, date, subject = line.split(_FIELD, 3)
            current = {"sha": sha, "parents": parents.split(), "date": date,
                       "subject": subject, "files": []}
            commits.append(current)
        elif line.strip() and current is not None:
            parts = line.split("\t")
            if len(parts) == 3:
                added, deleted, path = parts
                current["files"].append({
                    "path": path,
                    "added": None if added == "-" else int(added),
                    "deleted": None if deleted == "-" else int(deleted),
                })
    return commits


def score(commit: dict[str, Any], max_source_files: int = 4) -> dict[str, Any] | None:
    """Replay-worthiness. None = not a candidate; else the commit + why."""
    if len(commit["parents"]) != 1:
        return None  # merges have no single before; initial commits no before at all
    source = [row for row in commit["files"]
              if Path(row["path"]).suffix.lower() in _SOURCE_SUFFIXES
              and Path(row["path"]).name not in _NOISE_NAMES]
    if not source or len(source) > max_source_files:
        return None
    churn = sum((row["added"] or 0) + (row["deleted"] or 0) for row in source)
    if churn < 5:
        return None  # a one-line tweak is not a task
    fixish = bool(_FIX_WORDS.search(commit["subject"]))
    points = (3 if fixish else 0) + (2 if len(source) <= 2 else 1) + (1 if 10 <= churn <= 400 else 0)
    return {
        "sha": commit["sha"][:12],
        "date": commit["date"],
        "subject": commit["subject"],
        "source_files": [row["path"] for row in source],
        "churn": churn,
        "fixish_message": fixish,
        "score": points,
        "before_ref": f"{commit['sha'][:12]}^",
        "after_ref": commit["sha"][:12],
    }


def mine(repo: Path, limit: int = 400, max_source_files: int = 4) -> dict[str, Any]:
    raw = _git(repo, "log", f"--format={_LOG_FORMAT}", "--numstat",
               "--date=short", f"-{limit}")
    candidates = [row for row in (score(c, max_source_files) for c in parse_log(raw)) if row]
    candidates.sort(key=lambda row: (-row["score"], row["date"]), reverse=False)
    candidates.sort(key=lambda row: -row["score"])
    return {
        "schema_version": 1,
        "repo": repo.name,
        "commits_scanned": limit,
        "candidates": candidates,
        "note": ("ranked replay candidates; turning one into a fixture still requires judgement "
                 "(statable task, drivable surface, no answer leak) plus the admission gate"),
    }


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description="Rank a repo's commits by shadow-replay worthiness (read-only).")
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=400)
    parser.add_argument("--max-source-files", type=int, default=4)
    parser.add_argument("--top", type=int, default=15)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = mine(args.repo.resolve(), args.limit, args.max_source_files)
    if args.output:
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for row in result["candidates"][:args.top]:
        print(f"{row['score']}  {row['sha']}  {row['date']}  files={len(row['source_files'])} "
              f"churn={row['churn']}  {row['subject'][:80]}")
    print(f"\n{len(result['candidates'])} candidate(s) from {result['commits_scanned']} commits scanned")


if __name__ == "__main__":
    main()
