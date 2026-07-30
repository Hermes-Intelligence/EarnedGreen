#!/usr/bin/env python3
"""Independent, harness-authored verification checks (the forcing functions).

The objective/evidence ledgers are AGENT-authored: the pre-submit gate can only
re-execute what the agent chose to record, so it can never catch a requirement
the agent never enumerated (demonstrated: medi-ny paren-wrap missed by every
arm; therapeutic_class regression stochastic). This module is the other half:
a check suite authored by the HARNESS at prepare time and (re)run by the
harness itself, independent of the agent's claims.

Check kinds:
  acceptance    a command that must exit 0 (frozen spec acceptance tests,
                public test suites, owner-provided commands)
  differential  run the same command in the baseline snapshot and in the
                current workspace; any output difference not matched by an
                expected_change_patterns regex fails with a line/field diff
                (catches silent behavioral regressions deterministically)
  symbol-sweep  deterministic repo-wide reference sweep over symbols defined
                in changed files; referencing files the agent neither changed
                nor recorded as inspected fail the check (F-2026-07-12-013)
  property      a property/invariant script over data samples must exit 0
                (catches requirements that live in the DATA, not the task text)
  finding       an ingested independent-verifier finding; fails until a
                resolution names re-executable proof (F-2026-07-12-011)
  derived       mechanically derived predicates (diff projections from git
                history, or relation pins mined from the implementation) —
                the only check source measured to discriminate where
                mind-derived predicates failed

Tamper resistance: harness-authored checks carry a freeze digest recorded at
prepare time. The gate recomputes the digest over `authored_by == "harness"`
entries; removal or weakening fails closed. Agents may only ADD checks.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

CHECK_TIMEOUT = 180
# Raised from 50 MB after a real repository came in at 78.7 MB of TRACKED source
# and silently lost its differential checks and its necessity probe. 50 MB is not
# a large repository in 2026; a cap that fires on ordinary work is not a safety
# valve, it is a capability that switches itself off. Override per task with
# `awbp task --max-baseline-bytes N`.
BASELINE_MAX_BYTES = 512 * 1024 * 1024
_TEXT_SUFFIXES = {".py", ".md", ".txt", ".json", ".toml", ".cfg", ".ini", ".yaml", ".yml",
                  ".ps1", ".sh", ".sql", ".csv", ".tsv", ".xml", ".html", ".js", ".ts", ".rst"}
_EXCLUDED_DIRS = {".agentic", ".git", "__pycache__", ".pytest_cache", "node_modules"}
_PY_SYMBOL = re.compile(r"^\s*(?:def|class)\s+([A-Za-z_]\w*)", re.M)
_PRIVATE_OK = re.compile(r"^__\w+__$")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def load(path: Path) -> dict[str, Any]:
    return json.loads(_read_text(path))


def sha256_bytes(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def harness_freeze_sha256(suite: dict[str, Any]) -> str:
    """Digest over the harness-authored checks and the loop budgets.

    Budgets are inside the freeze so an agent cannot buy itself iterations or
    disable no-progress termination by editing config.
    """
    rows = [row for row in suite.get("checks", []) if row.get("authored_by") == "harness"]
    rows.sort(key=lambda row: str(row.get("id")))
    return hashlib.sha256(canonical({"checks": rows, "config": suite.get("config", {})}).encode("utf-8")).hexdigest().upper()


def _workspace_files(workspace: Path) -> list[Path]:
    rows = []
    for path in sorted(workspace.rglob("*")):
        if not path.is_file():
            continue
        if any(part in _EXCLUDED_DIRS for part in path.relative_to(workspace).parts):
            continue
        rows.append(path)
    return rows


def snapshot_baseline(workspace: Path, destination: Path, max_bytes: int = BASELINE_MAX_BYTES) -> dict[str, Any]:
    """Copy the pre-change workspace and record its inventory.

    The snapshot powers differential checks (run the BEFORE code on the same
    input) and the symbol sweep (what changed, which symbols existed before).
    Oversized workspaces record `snapshot: skipped` explicitly so a differential
    check later fails closed with a reason instead of silently not running.
    """
    files = _workspace_files(workspace)
    total = sum(path.stat().st_size for path in files)
    inventory = {path.relative_to(workspace).as_posix(): sha256_bytes(path) for path in files}
    record: dict[str, Any] = {
        "schema_version": 1,
        "total_bytes": total,
        "inventory": inventory,
    }
    if total > max_bytes:
        record["snapshot"] = "skipped-size-cap"
        record["max_bytes"] = max_bytes
        record["lost"] = ("differential checks and the necessity probe both need the "
                          "pre-change tree. Without it they cannot run at all, so a green "
                          "from here is a smaller claim than it looks.")
        record["remedy"] = (f"re-run with  awbp task --max-baseline-bytes {total + (total // 10)}  "
                            f"(this workspace is {total / 1048576:.1f} MB of tracked source)")
        # The remedy is also RECORDED AS A FACT whose consumer is `awbp task`
        # itself: the next task in this repo applies the raised cap without a
        # human retyping it. This is the store's whole argument - the knowledge
        # acts, instead of waiting to be read.
        try:
            import facts_store
            from datetime import datetime, timezone
            facts_store.store_for(workspace).record(
                "baseline-exceeds-default-cap", "repo-fact",
                f"tracked source is {total / 1048576:.1f} MB, above the default snapshot cap",
                source="harness_checks.snapshot_baseline",
                now=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                enforced_by="awbp task (auto-raises the cap from this fact)",
                data={"recommended_bytes": total + (total // 10)})
        except ImportError:
            pass
        return record
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    for path in files:
        target = destination / path.relative_to(workspace)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    record["snapshot"] = "complete"
    record["path"] = destination.name
    return record


def _portable_command(command: Any) -> Any:
    """python3 -> pinned interpreter on hosts without an executable python3 (Windows)."""
    if sys.platform != "win32" and shutil.which("python3"):
        return command
    if isinstance(command, list) and command and command[0] == "python3":
        return [sys.executable, *command[1:]]
    if isinstance(command, str) and re.match(r"^\s*python3(?=\s|$)", command):
        executable = subprocess.list2cmdline([sys.executable])
        return re.sub(r"^\s*python3(?=\s|$)", lambda _: executable, command, count=1)
    return command


def _run(command: Any, cwd: Path, extra_env: dict[str, str] | None = None) -> tuple[int | None, str, str]:
    executable_command = _portable_command(command)
    try:
        completed = subprocess.run(
            executable_command, cwd=cwd, shell=isinstance(executable_command, str),
            text=True, capture_output=True, encoding="utf-8", errors="replace", timeout=CHECK_TIMEOUT,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", **(extra_env or {})})
        return completed.returncode, completed.stdout or "", completed.stderr or ""
    except subprocess.TimeoutExpired:
        return None, "", f"timed out after {CHECK_TIMEOUT}s"
    except (FileNotFoundError, OSError) as exc:
        return None, "", f"{type(exc).__name__}: {exc}"


def _purge_bytecode(workspace: Path) -> None:
    """Delete cached bytecode before executing checks.

    A source file rewritten within the same second with the same size passes
    CPython's (mtime-seconds, size) .pyc validation, so a stale compile can
    silently mask a RED check as green (observed live: VALUE=1 -> VALUE=2).
    Bytecode is a derived artifact; purging it is always safe.
    """
    for directory in list(workspace.rglob("__pycache__")):
        shutil.rmtree(directory, ignore_errors=True)
    for stray in list(workspace.rglob("*.pyc")):
        try:
            stray.unlink()
        except OSError:
            pass


# --- check runners ----------------------------------------------------------------


def _check_acceptance(check: dict[str, Any], workspace: Path) -> list[dict[str, str]]:
    command = check.get("command")
    if not command:
        return [{"reason": "acceptance check names no command"}]
    exit_code, stdout, stderr = _run(command, workspace)
    if exit_code != 0:
        tail = (stdout + "\n" + stderr).strip()[-2000:]
        return [{"reason": f"command exited {exit_code}", "command": str(command), "output_tail": tail}]
    return []


def _normalize_output(text: str) -> list[str]:
    """Parse JSON when possible so key order never counts as a difference."""
    stripped = text.strip()
    if stripped.startswith(("{", "[")):
        try:
            parsed = json.loads(stripped)
            return json.dumps(parsed, ensure_ascii=False, sort_keys=True, indent=0).splitlines()
        except json.JSONDecodeError:
            pass
    return stripped.splitlines()


def _check_differential(check: dict[str, Any], workspace: Path, baseline_dir: Path | None,
                        baseline_record: dict[str, Any] | None) -> list[dict[str, str]]:
    command = check.get("command")
    if not command:
        return [{"reason": "differential check names no command"}]
    if baseline_dir is None or not baseline_dir.is_dir():
        state = (baseline_record or {}).get("snapshot", "missing")
        return [{"reason": f"baseline workspace unavailable ({state}); differential cannot run and fails closed"}]
    if isinstance(command, list):
        # HARNESS scripts live outside the baseline snapshot (.agentic is
        # excluded), so a workspace-relative script path would not resolve in
        # the baseline directory: absolutize those - and ONLY those. Product
        # files exist in both directories and must stay relative, so each side
        # runs its own version (that difference is the point of the check).
        command = [
            str((workspace / part).resolve())
            if isinstance(part, str) and (workspace / part).is_file() and not (baseline_dir / part).is_file()
            else part
            for part in command
        ]
    base_exit, base_out, base_err = _run(command, baseline_dir)
    if base_exit is None:
        return [{"reason": f"baseline execution error: {base_err}"}]
    cur_exit, cur_out, cur_err = _run(command, workspace)
    if cur_exit is None:
        return [{"reason": f"current execution error: {cur_err}"}]
    if cur_exit != 0 and base_exit == 0:
        return [{"reason": f"command passes on baseline but exits {cur_exit} on current workspace",
                 "output_tail": (cur_out + "\n" + cur_err).strip()[-2000:]}]
    expected = [re.compile(pattern) for pattern in check.get("expected_change_patterns", [])]
    diff_lines = [
        line for line in difflib.unified_diff(_normalize_output(base_out), _normalize_output(cur_out), lineterm="")
        if line[:1] in {"+", "-"} and line[:3] not in {"+++", "---"}
    ]
    unexpected = [line for line in diff_lines if not any(p.search(line) for p in expected)]
    if unexpected:
        return [{"reason": "output changed beyond the declared expected changes",
                 "unexpected_diff": "\n".join(unexpected[:80])}]
    return []


def _changed_paths(workspace: Path, baseline_inventory: dict[str, str]) -> dict[str, str]:
    """path -> one of changed|added|deleted, against the baseline inventory."""
    current = {path.relative_to(workspace).as_posix(): sha256_bytes(path) for path in _workspace_files(workspace)}
    states: dict[str, str] = {}
    for path, digest in current.items():
        if path not in baseline_inventory:
            states[path] = "added"
        elif baseline_inventory[path] != digest:
            states[path] = "changed"
    for path in baseline_inventory:
        if path not in current:
            states[path] = "deleted"
    return states


def _symbols_in(text: str) -> set[str]:
    return {name for name in _PY_SYMBOL.findall(text) if not _PRIVATE_OK.match(name)}


def _definition_spans(lines: list[str]) -> list[tuple[str, int, int]]:
    """(symbol, start, end) for each top-level-or-nested def/class block.

    A block runs from its `def`/`class` line to the next non-blank line indented
    at or above its own level.
    """
    spans: list[tuple[str, int, int]] = []
    for index, line in enumerate(lines):
        match = re.match(r"^(\s*)(?:def|class)\s+([A-Za-z_]\w*)", line)
        if not match:
            continue
        indent, name = len(match.group(1)), match.group(2)
        end = len(lines)
        for probe in range(index + 1, len(lines)):
            candidate = lines[probe]
            if not candidate.strip():
                continue
            if len(candidate) - len(candidate.lstrip()) <= indent:
                end = probe
                break
        # Trim trailing blank lines: a block ends at its last real statement.
        # Without this, the blank separators before the NEXT definition count as
        # part of this one, so inserting a new function below would flag the
        # untouched function above it.
        while end > index + 1 and not lines[end - 1].strip():
            end -= 1
        spans.append((name, index, end))
    return spans


def _touched_symbols(before: str, after: str) -> set[str]:
    """Symbols whose DEFINITION actually changed between two versions.

    Not "every symbol in a file the agent touched": adding `discount()` to a
    module does not change `total()`, so flagging every consumer of `total` is
    noise, and noise trains people to ignore the sweep. A symbol counts only
    when a changed line falls inside its definition block.
    """
    before_lines, after_lines = before.splitlines(), after.splitlines()
    matcher = difflib.SequenceMatcher(None, before_lines, after_lines)
    changed_after: set[int] = set()
    changed_before: set[int] = set()
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        # Blank-line churn changes no behaviour and must not touch a symbol.
        changed_after.update(line for line in range(j1, j2) if after_lines[line].strip())
        changed_before.update(line for line in range(i1, i2) if before_lines[line].strip())
    touched: set[str] = set()
    for name, start, end in _definition_spans(after_lines):
        if not _PRIVATE_OK.match(name) and any(start <= line < end for line in changed_after):
            touched.add(name)
    for name, start, end in _definition_spans(before_lines):
        if not _PRIVATE_OK.match(name) and any(start <= line < end for line in changed_before):
            touched.add(name)
    return touched


def _check_symbol_sweep(check: dict[str, Any], workspace: Path, baseline_dir: Path | None,
                        baseline_record: dict[str, Any] | None, evidence: dict[str, Any] | None) -> list[dict[str, str]]:
    inventory = (baseline_record or {}).get("inventory")
    if not inventory:
        return [{"reason": "no baseline inventory recorded; symbol sweep cannot run and fails closed"}]
    states = _changed_paths(workspace, inventory)
    touched = set(states)
    symbols: set[str] = set()
    for path, state in states.items():
        if not path.endswith(".py"):
            continue
        has_baseline = baseline_dir is not None and (baseline_dir / path).is_file()
        if state == "changed" and has_baseline:
            # Only symbols whose definition actually changed - not every symbol
            # that happens to live in a file the agent edited.
            symbols |= _touched_symbols(_read_text(baseline_dir / path), _read_text(workspace / path))
        elif state == "added":
            symbols |= _symbols_in(_read_text(workspace / path))
        elif state == "deleted" and has_baseline:
            symbols |= _symbols_in(_read_text(baseline_dir / path))
        elif state == "changed":
            symbols |= _symbols_in(_read_text(workspace / path))
    if not symbols:
        return []
    inspected = {row.get("path") for row in (evidence or {}).get("consumer_inspections", []) if str(row.get("note", "")).strip()}
    failures: list[dict[str, str]] = []
    pattern = re.compile(r"\b(" + "|".join(re.escape(name) for name in sorted(symbols)) + r")\b")
    for path in _workspace_files(workspace):
        rel = path.relative_to(workspace).as_posix()
        if rel in touched or rel in inspected or path.suffix.lower() not in _TEXT_SUFFIXES:
            continue
        hits = sorted(set(pattern.findall(_read_text(path))))
        if hits:
            failures.append({
                "reason": f"consumer file references touched symbols but was neither changed nor recorded as inspected: {rel}",
                "path": rel,
                "symbols": ", ".join(hits),
            })
    return failures


def _check_property(check: dict[str, Any], workspace: Path) -> list[dict[str, str]]:
    command = check.get("command")
    if not command:
        return [{"reason": "property check names no command"}]
    exit_code, stdout, stderr = _run(command, workspace)
    if exit_code != 0:
        tail = (stdout + "\n" + stderr).strip()[-2000:]
        return [{"reason": f"property violated (exit {exit_code})", "command": str(command), "output_tail": tail}]
    return []


E2E_BOOT_TIMEOUT = 60
E2E_POLL_SECONDS = 0.25


def _wait_until_ready(url: str, deadline: float, process: subprocess.Popen) -> str | None:
    """Poll until the app answers, it dies, or we run out of patience.

    Returns None when ready, else why not. Polling a real readiness URL rather
    than sleeping a fixed number of seconds is the difference between a check
    that fails on a slow machine and one that means something.
    """
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return f"the app exited with {process.returncode} before it was ready"
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if 200 <= response.status < 400:
                    return None
        except (urllib.error.URLError, OSError, ValueError):
            pass
        time.sleep(E2E_POLL_SECONDS)
    return f"the app was not ready at {url} within {E2E_BOOT_TIMEOUT}s"


def _terminate(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def _check_e2e(check: dict[str, Any], workspace: Path) -> list[dict[str, str]]:
    """Boot the app, drive it, tear it down.

    DELIBERATELY NOT COUPLED TO PLAYWRIGHT. The harness's job is boot -> ready ->
    run -> teardown; the `command` is whatever drives the app, and Playwright is
    simply the most likely one. That keeps this kind runnable (and tested) with
    no browser toolchain installed, and keeps a UI stack's choices out of the
    harness. The command must run WITHOUT a model: a check a model has to
    interpret is not a check.

    The app is always torn down, including when the drive command explodes -- a
    leaked server poisons every subsequent check with a port conflict and the
    failure looks like the agent's fault.
    """
    start = check.get("start")
    command = check.get("command")
    if not start:
        return [{"reason": "e2e check names no `start` command for the app under test"}]
    if not command:
        return [{"reason": "e2e check names no `command` to drive the app"}]
    ready_url = check.get("ready_url")
    if not ready_url:
        return [{"reason": "e2e check names no `ready_url`: without one the harness cannot know the "
                          "app is up, and a fixed sleep is a flake generator, not a check"}]

    started = _portable_command(start)
    try:
        process = subprocess.Popen(
            started, cwd=workspace, shell=isinstance(started, str),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            encoding="utf-8", errors="replace",
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(workspace)})
    except (FileNotFoundError, OSError) as error:
        return [{"reason": f"the app could not be started: {type(error).__name__}: {error}",
                 "command": str(start)}]
    try:
        timeout = int(check.get("boot_timeout") or E2E_BOOT_TIMEOUT)
        problem = _wait_until_ready(ready_url, time.monotonic() + timeout, process)
        if problem:
            return [{"reason": problem, "command": str(start),
                     "output_tail": _drain(process)[-2000:]}]
        exit_code, stdout, stderr = _run(command, workspace, extra_env={"PYTHONPATH": str(workspace)})
        if exit_code != 0:
            return [{"reason": f"the app did not behave as required (exit {exit_code})",
                     "command": str(command),
                     "output_tail": (stdout + "\n" + stderr).strip()[-2000:]}]
        return []
    finally:
        _terminate(process)


def _drain(process: subprocess.Popen) -> str:
    try:
        return process.communicate(timeout=5)[0] or ""
    except (subprocess.TimeoutExpired, ValueError):
        return ""


def _check_derived(check: dict[str, Any], workspace: Path) -> list[dict[str, str]]:
    """Mechanically derived predicates (layer 1: diff projections; layer 2:
    relation pins) as a first-class check kind.

    The pins and corpus are HOST-side files (absolute paths, sha-pinned via the
    check's `files` list like every other frozen artifact): the agent can no
    more weaken a derived predicate than any other harness check. Lazy import,
    fail closed: a workspace-side scaffold copy of this module without the
    oracle modules must refuse rather than vacuously pass.
    """
    layer = check.get("layer")
    pins_path, corpus_path = check.get("pins"), check.get("corpus")
    if layer not in ("diff", "relation") or not pins_path:
        return [{"reason": "derived check must name layer (diff|relation) and pins"}]
    try:
        if layer == "diff":
            import diff_oracle as oracle
        else:
            import relation_oracle as oracle
    except ImportError as error:
        return [{"reason": f"oracle modules unavailable here; a derived check cannot run and fails "
                           f"closed rather than passing vacuously ({error})"}]
    try:
        pins = load(Path(pins_path))
        if pins.get("capture_command"):
            # Self-describing pins: the file names how to CAPTURE this repo's
            # observable stream (any language, any driver), and the predicates
            # are plain projection expectations evaluated right here. This is
            # what decouples the derived kind from any one fixture's runtime.
            import diff_oracle
            command = [sys.executable if part == "{python}" else part
                       for part in pins["capture_command"]]
            exit_code, stdout, stderr = _run(command, workspace)
            if exit_code != 0:
                return [{"reason": f"derived capture command exited {exit_code}: {(stderr or stdout)[-300:]}"}]
            streams = json.loads(stdout)
            outcome = diff_oracle.evaluate(pins["predicates"], streams)
            red = outcome["red_predicate_ids"]
        elif not corpus_path:
            return [{"reason": "derived check must name a corpus, or its pins must carry a capture_command"}]
        elif layer == "diff":
            streams = oracle.capture(workspace, Path(corpus_path))
            outcome = oracle.evaluate(pins["admitted"], streams)
            red = outcome["red_predicate_ids"]
        else:
            outcome = oracle.evaluate(pins["pins"], workspace, Path(corpus_path))
            red = outcome["red_pin_ids"]
    except (RuntimeError, KeyError, OSError, json.JSONDecodeError) as error:
        return [{"reason": f"derived-check execution error (fails closed): {type(error).__name__}: {error}"}]
    failures = [{"reason": f"derived predicate violated: {pid}", "predicate": pid} for pid in red]
    failures += [{"reason": f"derived predicate errored: {row}"} for row in outcome.get("errors", [])]
    return failures


def _check_finding(check: dict[str, Any], workspace: Path, resolutions: dict[str, Any]) -> list[dict[str, str]]:
    """A verifier finding stays failing until its resolution re-executes green.

    A resolution must name a command proving the finding is addressed (or an
    explicit owner waiver). Prose alone never resolves a finding: that would
    reintroduce self-attestation through the back door.
    """
    finding_id = str(check.get("id"))
    row = resolutions.get(finding_id)
    if not row:
        return [{"reason": f"unresolved independent-verifier finding: {check.get('claim', finding_id)}"}]
    if str(row.get("waived_by", "")).strip() and str(row.get("reason", "")).strip():
        return []
    command = row.get("command")
    if not command:
        return [{"reason": f"finding resolution has neither a proving command nor an owner waiver: {finding_id}"}]
    exit_code, stdout, stderr = _run(command, workspace)
    if exit_code != 0:
        return [{"reason": f"finding resolution command exited {exit_code}: {finding_id}",
                 "output_tail": (stdout + "\n" + stderr).strip()[-2000:]}]
    return []


def _verify_check_files(check: dict[str, Any], workspace: Path) -> list[dict[str, str]]:
    """Pin declared check scripts by sha256: a rewritten script fails closed."""
    failures = []
    for row in check.get("files", []):
        declared = Path(str(row.get("path", "")))
        target = declared if declared.is_absolute() else workspace / declared
        if not target.is_file():
            failures.append({"reason": f"check script missing: {row.get('path')}"})
        elif sha256_bytes(target) != str(row.get("sha256", "")).upper():
            failures.append({"reason": f"check script was modified after freeze: {row.get('path')}"})
    return failures


def run_suite(suite: dict[str, Any], workspace: Path, evidence: dict[str, Any] | None = None,
              baseline_record: dict[str, Any] | None = None, baseline_dir: Path | None = None,
              resolutions: dict[str, Any] | None = None) -> dict[str, Any]:
    workspace = Path(workspace)
    agentic = workspace / ".agentic"
    if baseline_record is None:
        candidate = agentic / "baseline-record.json"
        baseline_record = load(candidate) if candidate.is_file() else None
    if baseline_dir is None:
        name = (baseline_record or {}).get("path")
        candidate_dir = agentic / name if name else agentic / "baseline-workspace"
        baseline_dir = candidate_dir if candidate_dir.is_dir() else None
    if evidence is None:
        candidate = agentic / "evidence.json"
        evidence = load(candidate) if candidate.is_file() else None
    if resolutions is None:
        candidate = agentic / "finding-resolutions.json"
        resolutions = load(candidate).get("resolutions", {}) if candidate.is_file() else {}

    _purge_bytecode(workspace)
    results = []
    for check in suite.get("checks", []):
        kind = check.get("kind")
        integrity = _verify_check_files(check, workspace)
        if integrity:
            results.append({
                "id": check.get("id"), "kind": kind,
                "authored_by": check.get("authored_by", "harness"),
                "verdict": "FAIL", "failures": integrity,
            })
            continue
        if kind == "acceptance":
            failures = _check_acceptance(check, workspace)
        elif kind == "differential":
            failures = _check_differential(check, workspace, baseline_dir, baseline_record)
        elif kind == "symbol-sweep":
            failures = _check_symbol_sweep(check, workspace, baseline_dir, baseline_record, evidence)
        elif kind == "property":
            failures = _check_property(check, workspace)
        elif kind == "e2e":
            failures = _check_e2e(check, workspace)
        elif kind == "derived":
            failures = _check_derived(check, workspace)
        elif kind == "finding":
            failures = _check_finding(check, workspace, resolutions)
        else:
            failures = [{"reason": f"unknown check kind: {kind!r}"}]
        row = {
            "id": check.get("id"),
            "kind": kind,
            "authored_by": check.get("authored_by", "harness"),
            "verdict": "PASS" if not failures else "FAIL",
            "failures": failures,
        }
        # Knowledge attaches to FAILURES, not to the prompt: a failing check
        # carries its harness-authored guidance (conventions excerpt, fix
        # direction) so the loop's feedback teaches exactly what is broken.
        if failures and check.get("guidance"):
            row["guidance"] = check["guidance"]
        results.append(row)
    failing = [row for row in results if row["verdict"] != "PASS"]
    fingerprint = hashlib.sha256(canonical(
        [{"id": row["id"], "failures": [f.get("reason") for f in row["failures"]]} for row in failing]
    ).encode("utf-8")).hexdigest().upper()
    return {
        "schema_version": 1,
        "green": not failing,
        "checks": results,
        "failing_check_ids": [row["id"] for row in failing],
        "failure_fingerprint": fingerprint,
    }


def verify_suite_integrity(suite: dict[str, Any]) -> list[str]:
    """Structural + tamper checks the gate runs before trusting the suite."""
    problems: list[str] = []
    if not isinstance(suite.get("checks"), list) or not suite["checks"]:
        problems.append("check suite is empty")
        return problems
    seen: set[str] = set()
    for row in suite["checks"]:
        check_id = str(row.get("id") or "")
        if not check_id:
            problems.append("a check has no id")
        elif check_id in seen:
            problems.append(f"duplicate check id: {check_id}")
        seen.add(check_id)
    recorded = str(suite.get("harness_freeze_sha256") or "")
    if not recorded:
        problems.append("suite has no harness_freeze_sha256 (harness-authored checks are not frozen)")
    elif harness_freeze_sha256(suite) != recorded:
        problems.append("harness-authored checks or budgets were modified after freeze (digest mismatch)")
    if not any(row.get("authored_by") == "harness" for row in suite["checks"]):
        problems.append("suite contains no harness-authored checks")
    return problems


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    snap = sub.add_parser("baseline", help="snapshot the pre-change workspace")
    snap.add_argument("--workspace", type=Path, required=True)
    snap.add_argument("--output-dir", type=Path, required=True, help=".agentic directory")
    run = sub.add_parser("run", help="run the check suite once")
    run.add_argument("--suite", type=Path, required=True)
    run.add_argument("--workspace", type=Path, required=True)
    run.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.action == "baseline":
        record = snapshot_baseline(args.workspace.resolve(), args.output_dir / "baseline-workspace")
        (args.output_dir / "baseline-record.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"snapshot": record["snapshot"], "files": len(record["inventory"])}, indent=2))
        return
    suite = load(args.suite)
    problems = verify_suite_integrity(suite)
    if problems:
        print(json.dumps({"green": False, "integrity_failures": problems}, ensure_ascii=False, indent=2))
        raise SystemExit(1)
    report = run_suite(suite, args.workspace.resolve())
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    raise SystemExit(0 if report["green"] else 1)


if __name__ == "__main__":
    main()
