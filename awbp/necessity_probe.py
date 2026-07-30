#!/usr/bin/env python3
"""Is the green EARNED? Revert each hunk and demand that some check notices.

A green suite means "the checks passed". It does not mean the checks could have
failed. SpecBench (arXiv 2605.21384) measures that a saturated visible suite is
where reward hacking hides rather than where it is absent, and PBT-Bench (arXiv
2605.15229) measures that agent-derived checks miss 17-58% of seeded bugs. We
cannot fix that miss rate. We CAN measure a suite's discriminating power over
the change actually made, and refuse to certify when it is decorative.

The mechanism: the harness holds the pre-change baseline AND the agent's diff.
So revert ONE hunk at a time and re-run the suite.

  some check turns red  -> that hunk is NECESSARY: something tests it
  no check turns red    -> UNCOVERED: the hunk is either unneeded or untested
  everything errors out -> INCONCLUSIVE: the revert broke the code structurally
                           (e.g. half a function), so the red proves nothing

Chosen over classic mutation testing (PIT/Stryker/mutmut) deliberately: this
operates on the DIFF, not the AST, so it is language-agnostic, needs no
per-ecosystem dependency, is deterministic, and its message is directly
actionable - "reverting src/api.py:40-48 breaks no check".

Zero model calls.
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import harness_checks

# Only BEHAVIOURAL checks can answer "is this hunk necessary". The symbol sweep
# asks whether the AGENT inspected consumers and a finding check asks whether a
# verifier's issue was resolved: neither is a function of the code under revert,
# and including them reddens every revert and certifies anything.
_BEHAVIOURAL_KINDS = {"acceptance", "differential", "property"}


def _compiles(path: Path) -> bool:
    """Does this file still parse? Distinguishes a broken revert from a real red."""
    if path.suffix != ".py":
        return True
    try:
        compile(path.read_text(encoding="utf-8-sig", errors="replace"), str(path), "exec")
        return True
    except (SyntaxError, ValueError):
        return False

_EXCLUDED_DIRS = {".agentic", ".git", "__pycache__", ".pytest_cache", "node_modules"}
# A hunk of only these is never load-bearing for behaviour, so never flagged.
_COMMENT_PREFIXES = ("#", "//", "/*", "*", "*/", "--", '"""', "'''")


def _read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8-sig", errors="replace").splitlines()


def is_substantive(lines: list[str]) -> bool:
    """Does this block contain anything that can change behaviour?"""
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(_COMMENT_PREFIXES):
            continue
        # An import-only hunk is wiring, not behaviour; it is covered
        # transitively by whatever uses it.
        if re.match(r"^(import|from)\s+\w", stripped):
            continue
        return True
    return False


def suite_owned_paths(suite: dict[str, Any], workspace: Path) -> set[str]:
    """Files that belong to the CHECK SUITE, not to the agent's change.

    Check scripts are part of the measuring instrument. Probing them would ask
    "is this check necessary for a check to pass", which is meaningless and, on
    a suite whose scripts sit inside the workspace, would silently inflate the
    uncovered count. Production keeps them in .agentic/ (already excluded); this
    covers every other placement.
    """
    owned: set[str] = set()
    for check in suite.get("checks", []):
        for row in check.get("files", []):
            owned.add(str(row.get("path", "")).replace("\\", "/"))
        command = check.get("command")
        parts = command if isinstance(command, list) else str(command or "").split()
        for part in parts:
            candidate = Path(str(part))
            # Only WORKSPACE-RELATIVE files can be owned by the suite. `workspace /
            # <absolute>` yields the absolute path back, so a command naming an
            # absolute interpreter (which is how the detected runner is pinned on
            # Windows) would claim python.exe as a check script.
            if candidate.is_absolute() or ".." in candidate.parts:
                continue
            if candidate.suffix and (workspace / candidate).is_file():
                owned.add(candidate.as_posix())
    return {path for path in owned if path}


def changed_files(baseline_dir: Path, workspace: Path, exclude: set[str] | None = None) -> list[str]:
    exclude = exclude or set()
    rows: list[str] = []
    for path in sorted(workspace.rglob("*")):
        if not path.is_file() or any(part in _EXCLUDED_DIRS for part in path.relative_to(workspace).parts):
            continue
        if path.suffix in {".pyc", ".pdf", ".png"}:
            continue
        rel = path.relative_to(workspace).as_posix()
        if rel in exclude:
            continue
        base = baseline_dir / rel
        if not base.is_file():
            rows.append(rel)  # added file: every hunk is new
        else:
            try:
                if _read_lines(base) != _read_lines(path):
                    rows.append(rel)
            except (OSError, UnicodeDecodeError):
                continue
    return rows


_DEF_START = re.compile(r"^(\s*)(?:def|class)\s+[A-Za-z_]\w*")


def _split_points(lines: list[str], offset: int) -> list[int]:
    """Absolute indices where a new definition begins inside an inserted block."""
    starts = [offset + index for index, line in enumerate(lines) if _DEF_START.match(line)]
    return [start for start in starts if start > offset]


def hunks_for(baseline_dir: Path, workspace: Path, rel: str) -> list[dict[str, Any]]:
    """Line-level hunks between the baseline and current version of one file.

    Pure insertions are SPLIT at definition boundaries. difflib merges adjacent
    added lines into one opcode, so appending `discount()` and `apply_coupon()`
    together yields a single hunk: reverting it removes both, the test for
    `discount` fails, and the untested `apply_coupon` is scored "necessary" -
    hiding inside its tested neighbour. That is precisely the code the probe
    exists to surface, so the granularity must follow definitions, not diff
    adjacency. Replacements are left whole: which baseline lines correspond to
    which sub-range is ambiguous, and a wrong split would fabricate findings.
    """
    base = baseline_dir / rel
    current = workspace / rel
    before = _read_lines(base) if base.is_file() else []
    after = _read_lines(current)
    matcher = difflib.SequenceMatcher(None, before, after)
    rows: list[dict[str, Any]] = []
    for index, (tag, i1, i2, j1, j2) in enumerate(matcher.get_opcodes()):
        if tag == "equal":
            continue
        segments: list[tuple[int, int]] = [(j1, j2)]
        if tag == "insert" or i1 == i2:
            boundaries = _split_points(after[j1:j2], j1)
            if boundaries:
                edges = [j1, *boundaries, j2]
                segments = [(edges[k], edges[k + 1]) for k in range(len(edges) - 1) if edges[k] < edges[k + 1]]
        for part, (s1, s2) in enumerate(segments):
            rows.append({
                "hunk_id": f"{rel}#{index}" + (f".{part}" if len(segments) > 1 else ""),
                "path": rel,
                "tag": tag,
                "baseline_span": [i1, i2] if len(segments) == 1 else [i1, i1],
                "current_span": [s1, s2],
                "current_lines": after[s1:s2],
                "baseline_lines": before[i1:i2] if len(segments) == 1 else [],
                "substantive": is_substantive(after[s1:s2]) or (len(segments) == 1 and is_substantive(before[i1:i2])),
            })
    return rows


def revert_hunk(baseline_dir: Path, workspace: Path, destination: Path, hunk: dict[str, Any]) -> None:
    """Copy the workspace to `destination` with exactly this hunk reverted."""
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(workspace, destination, ignore=shutil.ignore_patterns(*_EXCLUDED_DIRS))
    rel = hunk["path"]
    base = baseline_dir / rel
    before = _read_lines(base) if base.is_file() else []
    after = _read_lines(workspace / rel)
    i1, i2 = hunk["baseline_span"]
    j1, j2 = hunk["current_span"]
    reverted = after[:j1] + before[i1:i2] + after[j2:]
    target = destination / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(reverted) + "\n", encoding="utf-8")


def probe(suite: dict[str, Any], baseline_dir: Path, workspace: Path,
          evidence: dict[str, Any] | None = None, max_hunks: int = 40) -> dict[str, Any]:
    baseline_dir, workspace = Path(baseline_dir), Path(workspace)
    # The REAL baseline inventory, not an empty one. With an empty inventory the
    # symbol sweep treats every file as newly added, so it reddens on every
    # revert and scores every hunk "necessary" - the probe would certify
    # anything. (Found on the first fresh-repo run.)
    baseline_record = {
        "inventory": {
            path.relative_to(baseline_dir).as_posix(): harness_checks.sha256_bytes(path)
            for path in harness_checks._workspace_files(baseline_dir)
        },
        "snapshot": "complete",
        "path": baseline_dir.name,
    }
    behavioural = dict(suite, checks=[c for c in suite.get("checks", []) if c.get("kind") in _BEHAVIOURAL_KINDS])
    behavioural["harness_freeze_sha256"] = harness_checks.harness_freeze_sha256(behavioural)
    if not behavioural["checks"]:
        return {"schema_version": 1, "earned": False, "necessity_ratio": None, "hunks": [], "uncovered_hunks": [],
                "hunks_total": 0, "hunks_substantive": 0, "hunks_probed": 0, "truncated": False,
                "necessary": 0, "uncovered": 0, "inconclusive_structural": 0,
                "problem": "the suite has no behavioural check, so necessity cannot be measured at all"}
    owned = suite_owned_paths(suite, workspace)
    all_hunks: list[dict[str, Any]] = []
    for rel in changed_files(baseline_dir, workspace, exclude=owned):
        all_hunks.extend(hunks_for(baseline_dir, workspace, rel))
    substantive = [h for h in all_hunks if h["substantive"]]
    rows: list[dict[str, Any]] = []
    truncated = len(substantive) > max_hunks
    for hunk in substantive[:max_hunks]:
        with tempfile.TemporaryDirectory(prefix="necessity-") as temp:
            destination = Path(temp) / "reverted"
            revert_hunk(baseline_dir, workspace, destination, hunk)
            # A revert that leaves the file unparseable proves nothing: the red
            # would be about broken syntax, not about coverage. Decide this by
            # actually compiling the file, not by pattern-matching the output -
            # an ImportError because the reverted function is GONE is exactly
            # the signal we want to count.
            if not _compiles(destination / hunk["path"]):
                verdict, failures = "inconclusive-structural", []
            else:
                report = harness_checks.run_suite(behavioural, destination, evidence=evidence,
                                                  baseline_record=baseline_record, baseline_dir=baseline_dir)
                failures = [row for row in report["checks"] if row["verdict"] != "PASS"]
                verdict = "necessary" if failures else "uncovered"
        rows.append({
            "hunk_id": hunk["hunk_id"], "path": hunk["path"],
            "current_span": hunk["current_span"],
            "verdict": verdict,
            "reddened_checks": [row["id"] for row in failures],
            "preview": "\n".join(hunk["current_lines"][:3])[:200],
        })
    necessary = [row for row in rows if row["verdict"] == "necessary"]
    uncovered = [row for row in rows if row["verdict"] == "uncovered"]
    inconclusive = [row for row in rows if row["verdict"] == "inconclusive-structural"]
    decidable = len(necessary) + len(uncovered)

    # A probe with nothing to probe is not a pass. `earned = not uncovered` is
    # vacuously true when the change is empty, so an untouched workspace used to
    # print EARNED - which is the exact defect this whole tool exists to catch,
    # in the tool itself, on the path the README sends a stranger down. There is
    # no verdict to give about a change that does not exist.
    if not substantive:
        return {
            "schema_version": 1, "earned": False, "nothing_to_probe": True,
            "hunks_total": len(all_hunks), "hunks_substantive": 0, "hunks_probed": 0,
            "truncated": False, "necessary": 0, "uncovered": 0,
            "inconclusive_structural": 0, "necessity_ratio": None,
            "uncovered_hunks": [], "hunks": [],
            "reason": ("no substantive change to probe. This is NOT a pass: the question "
                       "'is this green earned' has no meaning when nothing was changed. "
                       "Implement first, then probe."),
            "rule": "a probe over an empty diff proves nothing and must not report earned",
        }

    return {
        "schema_version": 1,
        "nothing_to_probe": False,
        "hunks_total": len(all_hunks),
        "hunks_substantive": len(substantive),
        "hunks_probed": len(rows),
        "truncated": truncated,
        "necessary": len(necessary),
        "uncovered": len(uncovered),
        "inconclusive_structural": len(inconclusive),
        "necessity_ratio": (len(necessary) / decidable) if decidable else None,
        "earned": not uncovered,
        "uncovered_hunks": uncovered,
        "hunks": rows,
        "rule": ("every substantive hunk of the change must be necessary for at least one check; an uncovered hunk is "
                 "either unneeded code or untested code, and both are worth surfacing"),
        "policy": ("standard: report uncovered hunks and require a check or an explicit note. "
                   "critical: an uncovered substantive hunk fails the gate - nothing reaches a human gate with "
                   "unexplained, untested code in the diff."),
    }


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-hunks", type=int, default=40)
    args = parser.parse_args()
    suite = json.loads(args.suite.read_text(encoding="utf-8-sig"))
    evidence = json.loads(args.evidence.read_text(encoding="utf-8-sig")) if args.evidence else None
    result = probe(suite, args.baseline, args.workspace, evidence=evidence, max_hunks=args.max_hunks)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    raise SystemExit(0 if result["earned"] else 1)


if __name__ == "__main__":
    main()
