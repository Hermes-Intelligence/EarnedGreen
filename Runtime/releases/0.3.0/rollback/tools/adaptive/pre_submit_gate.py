#!/usr/bin/env python3
"""Fail-closed task completion gate using objective and evidence ledgers.

The gate does not trust recorded outcomes. It:
  * rejects an empty or schema-invalid objective ledger;
  * verifies the ledger's ``task_sha256`` against the real task file;
  * requires every ``verification_runs`` entry and every ``test``/``migration``
    evidence item to name a command AND record ``exit_code == 0``;
  * actually re-executes each recorded command via subprocess and compares the
    observed exit code (and, when recorded, an output hash) against the claim.
Any missing, mismatched, or failing re-execution turns the verdict into FAIL.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REEXEC_TIMEOUT = 120
_RUN_KINDS = {"test", "migration"}


def _portable_command(command: Any) -> Any:
    """Resolve the common Python 3 launcher across the execution boundary.

    Provider evidence is commonly recorded inside Linux as ``python3 ...`` while
    the host-side final gate runs on Windows, where only the pinned interpreter
    may exist. Replacing only the leading executable preserves the command and
    keeps re-execution fail-closed without treating an OS alias as product failure.
    """
    # Windows may expose a python3 shim/alias that ``which`` can see but which
    # returns cmd.exe exit 9009 when invoked. Always use the pinned interpreter
    # on Windows; presence alone is not proof that the alias is executable.
    if sys.platform != "win32" and shutil.which("python3"):
        return command
    if isinstance(command, list) and command and command[0] == "python3":
        return [sys.executable, *command[1:]]
    if isinstance(command, str) and re.match(r"^\s*python3(?=\s|$)", command):
        executable = subprocess.list2cmdline([sys.executable])
        return re.sub(r"^\s*python3(?=\s|$)", lambda _: executable, command, count=1)
    return command


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256(path: Path) -> str:
    """Digest raw bytes (used for protected-file baselines)."""
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def task_text_sha256(path: Path) -> str:
    """Digest the decoded task text the same way objective_compiler does."""
    return hashlib.sha256(path.read_text(encoding="utf-8-sig").encode("utf-8")).hexdigest().upper()


def find_ledger_schema() -> dict[str, Any] | None:
    for base in (HERE, *HERE.parents):
        candidate = base / "schemas" / "objective-ledger.schema.json"
        if candidate.exists():
            return json.loads(candidate.read_text(encoding="utf-8-sig"))
    return None


_JSON_TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
}


def _schema_errors(instance: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    """Minimal JSON-Schema subset validator (type/required/const/enum/pattern/minimum/items/properties)."""
    errors: list[str] = []
    expected = schema.get("type")
    if expected:
        if expected == "integer" and isinstance(instance, bool):
            errors.append(f"{path}: expected integer, got boolean")
        elif not isinstance(instance, _JSON_TYPES[expected]) or (expected == "number" and isinstance(instance, bool)):
            errors.append(f"{path}: expected {expected}")
            return errors
    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: must equal {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance!r} not in {schema['enum']}")
    if "pattern" in schema and isinstance(instance, str) and not re.search(schema["pattern"], instance):
        errors.append(f"{path}: does not match {schema['pattern']}")
    if "minimum" in schema and isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if instance < schema["minimum"]:
            errors.append(f"{path}: below minimum {schema['minimum']}")
    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}.{key}: required property missing")
        for key, subschema in schema.get("properties", {}).items():
            if key in instance:
                errors.extend(_schema_errors(instance[key], subschema, f"{path}.{key}"))
    if isinstance(instance, list) and "items" in schema:
        for index, element in enumerate(instance):
            errors.extend(_schema_errors(element, schema["items"], f"{path}[{index}]"))
    return errors


def _reexecute(command: Any, workspace: Path, cache: dict[Any, tuple]) -> tuple[int | None, str | None, str | None]:
    """Run a recorded command in the workspace. Returns (exit_code, output_sha256, error)."""
    key = tuple(command) if isinstance(command, list) else command
    if key in cache:
        return cache[key]
    executable_command = _portable_command(command)
    try:
        if isinstance(executable_command, list):
            completed = subprocess.run(executable_command, cwd=workspace, text=True, capture_output=True, encoding="utf-8", errors="replace", timeout=REEXEC_TIMEOUT)
        else:
            completed = subprocess.run(executable_command, cwd=workspace, shell=True, text=True, capture_output=True, encoding="utf-8", errors="replace", timeout=REEXEC_TIMEOUT)
        digest = hashlib.sha256(((completed.stdout or "") + (completed.stderr or "")).encode("utf-8", "replace")).hexdigest().upper()
        result = (completed.returncode, digest, None)
    except subprocess.TimeoutExpired:
        result = (None, None, f"timed out after {REEXEC_TIMEOUT}s")
    except FileNotFoundError as exc:
        result = (None, None, f"command not found: {exc}")
    except OSError as exc:
        result = (None, None, f"{type(exc).__name__}: {exc}")
    cache[key] = result
    return result


def _verify_command_entry(entry: dict[str, Any], scope_id: str, workspace: Path, cache: dict[Any, tuple],
                          failures: list[dict[str, str]], reexecute: bool) -> None:
    command = entry.get("command")
    if not command:
        failures.append({"id": scope_id, "reason": "evidence/verification entry names no re-executable command"})
        return
    if "exit_code" not in entry:
        failures.append({"id": scope_id, "reason": f"recorded run omits exit_code: {command}"})
        return
    if entry["exit_code"] != 0:
        failures.append({"id": scope_id, "reason": f"recorded exit_code {entry['exit_code']} != 0: {command}"})
        return
    if not reexecute:
        return
    actual_exit, actual_hash, error = _reexecute(command, workspace, cache)
    if error is not None:
        failures.append({"id": scope_id, "reason": f"re-execution error for '{command}': {error}"})
        return
    if actual_exit != 0:
        failures.append({"id": scope_id, "reason": f"re-execution failed (observed exit {actual_exit}): {command}"})
        return
    if actual_exit != entry["exit_code"]:
        failures.append({"id": scope_id, "reason": f"re-execution exit {actual_exit} != recorded {entry['exit_code']}: {command}"})
        return
    recorded_hash = entry.get("output_sha256")
    if recorded_hash and str(recorded_hash).upper() != actual_hash:
        failures.append({"id": scope_id, "reason": f"re-execution output hash mismatch: {command}"})


def _spec_first_checks(spec: dict[str, Any], spec_freeze: dict[str, Any] | None,
                       evidence: dict[str, Any], workspace: Path, resolved_task: Path | None,
                       failures: list[dict[str, str]], cache: dict[Any, tuple], reexecute: bool) -> None:
    """Spec-first completion controls: validated spec, intact ledger freeze
    (anti-scope-shrink), and re-executed acceptance tests."""
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    try:
        import spec_synthesis
    except ImportError:
        failures.append({"id": "spec-synthesis", "reason": "spec.json present but the spec_synthesis module is unavailable to the gate"})
        return
    task_text = resolved_task.read_text(encoding="utf-8-sig") if resolved_task and resolved_task.is_file() else None
    outcome = spec_synthesis.validate_spec(spec, Path(workspace), task_text)
    for failure in outcome["failures"]:
        failures.append({"id": f"spec:{failure['id']}", "reason": failure["reason"]})

    # (b) Ledger freeze: recompute the freeze hash and compare against the record
    # made at spec time. Any removal, rewrite or downgrade of a frozen requirement
    # without an explicit owner_scope_change entry fails; additions are allowed.
    if spec_freeze is None:
        failures.append({"id": "spec-freeze", "reason": "no spec-freeze record: the frozen ledger was never recorded (run spec_synthesis validate --freeze)"})
    else:
        recorded = str(spec_freeze.get("spec_sha256") or "")
        if spec_synthesis.spec_freeze_sha256(spec) != recorded:
            # The hash may legitimately differ on additions; the row-level check
            # below is authoritative for shrink/downgrade.
            for violation in spec_synthesis.freeze_violations(spec, spec_freeze):
                failures.append({"id": "spec-freeze", "reason": violation})
        frozen_ids = {row.get("id") for row in spec_freeze.get("requirements", [])}
        approved = {
            row.get("requirement_id")
            for row in spec.get("frozen_ledger", {}).get("owner_scope_changes", [])
            if str(row.get("approved_by", "")).strip() and str(row.get("reason", "")).strip()
        }
        for row in evidence.get("requirements", []):
            requirement_id = row.get("requirement_id")
            if requirement_id in frozen_ids and row.get("status") in {"not_applicable", "rejected"} and requirement_id not in approved:
                failures.append({"id": requirement_id, "reason": f"frozen requirement downgraded to {row.get('status')!r} in evidence without an owner_scope_change entry"})

    # (c) Every acceptance test is re-executed by the gate and must pass.
    for test in spec.get("acceptance_tests", []):
        entry = {"command": test.get("command"), "exit_code": 0}
        _verify_command_entry(entry, f"acceptance:{test.get('id', '<missing-id>')}", Path(workspace), cache, failures, reexecute)


def validate(ledger: dict[str, Any], evidence: dict[str, Any], workspace: Path,
             baseline: dict[str, Any] | None = None, task_path: Path | None = None,
             schema: dict[str, Any] | None = None, reexecute: bool = True,
             impact_map: dict[str, Any] | None = None,
             checkpoint: dict[str, Any] | None = None,
             handoff: dict[str, Any] | None = None,
             spec: dict[str, Any] | None = None,
             spec_freeze: dict[str, Any] | None = None) -> dict[str, Any]:
    failures: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    workspace = Path(workspace)
    cache: dict[Any, tuple] = {}

    # (d) Ledger must be non-empty and structurally valid before anything is trusted.
    schema = schema if schema is not None else find_ledger_schema()
    if schema is not None:
        for error in _schema_errors(ledger, schema):
            failures.append({"id": "ledger-schema", "reason": error})
    else:
        if ledger.get("schema_version") != 2 or not isinstance(ledger.get("task_sha256"), str):
            failures.append({"id": "ledger-schema", "reason": "ledger missing schema_version==2 or task_sha256"})
    if not ledger.get("requirements"):
        failures.append({"id": "ledger-requirements", "reason": "objective ledger has no requirements"})

    # (e) Verify the ledger's task_sha256 against the real task file.
    resolved_task: Path | None = None
    if task_path is not None:
        resolved_task = Path(task_path)
    elif ledger.get("source"):
        candidate = Path(ledger["source"])
        for probe in (candidate, workspace / candidate):
            if probe.is_file():
                resolved_task = probe
                break
    declared_sha = ledger.get("task_sha256")
    if resolved_task and resolved_task.is_file():
        actual_sha = task_text_sha256(resolved_task)
        if declared_sha and actual_sha != declared_sha:
            failures.append({"id": "task-sha256", "reason": f"ledger task_sha256 does not match {resolved_task}"})
    elif task_path is not None:
        failures.append({"id": "task-sha256", "reason": f"task file not found for verification: {task_path}"})
    else:
        warnings.append({"id": "task-sha256", "reason": "task file not resolvable; sha256 not independently verified"})

    evidence_rows = {row.get("requirement_id"): row for row in evidence.get("requirements", [])}
    for req in ledger.get("requirements", []):
        row = evidence_rows.get(req["id"])
        if not row:
            failures.append({"id": req["id"], "reason": "missing evidence row"})
            continue
        status = row.get("status")
        if status == "not_applicable":
            if not str(row.get("reason", "")).strip():
                failures.append({"id": req["id"], "reason": "not_applicable without reason"})
            continue
        if status != "verified":
            failures.append({"id": req["id"], "reason": f"status is {status or 'missing'}, not verified"})
            continue
        items = row.get("evidence", [])
        if not items:
            failures.append({"id": req["id"], "reason": "verified without evidence"})
            continue
        observed_kinds = set()
        for item in items:
            kind = item.get("kind")
            observed_kinds.add(kind)
            if "exit_code" in item and item["exit_code"] != 0:
                failures.append({"id": req["id"], "reason": f"evidence command failed: {item.get('command','unknown')}"})
            # (c) test/migration evidence must name a command the gate re-executes.
            if kind in _RUN_KINDS:
                _verify_command_entry(item, req["id"], workspace, cache, failures, reexecute)
            if item.get("path"):
                target = (workspace / item["path"]).resolve()
                try:
                    target.relative_to(workspace.resolve())
                except ValueError:
                    failures.append({"id": req["id"], "reason": f"evidence path escapes workspace: {item['path']}"})
                    continue
                if not target.exists():
                    failures.append({"id": req["id"], "reason": f"evidence path missing: {item['path']}"})
        required = set(req.get("evidence_required", [])) - {"behavior"}
        missing = sorted(required - observed_kinds)
        if missing:
            failures.append({"id": req["id"], "reason": "missing evidence kinds: " + ", ".join(missing)})

    resolutions = {row.get("ambiguity_id"): row for row in evidence.get("ambiguity_resolutions", [])}
    for ambiguity in ledger.get("ambiguities", []):
        if not ambiguity.get("material"):
            continue
        resolution = resolutions.get(ambiguity["id"])
        if not resolution or not str(resolution.get("resolution", "")).strip() or not str(resolution.get("authority", "")).strip():
            failures.append({"id": ambiguity["id"], "reason": "material ambiguity lacks an authoritative resolution"})

    # (a)+(b) Verification runs must be present, claim success, and re-execute successfully.
    runs = evidence.get("verification_runs", [])
    if not runs:
        failures.append({"id": "verification-runs", "reason": "no verification command recorded"})
    for run in runs:
        _verify_command_entry(run, "verification-runs", workspace, cache, failures, reexecute)

    if baseline:
        for protected in baseline.get("protected_files", []):
            target = workspace / protected["path"]
            if not target.exists() or sha256(target) != protected["sha256"]:
                failures.append({"id": "protected-files", "reason": f"protected file changed: {protected['path']}"})
    claim = evidence.get("completion_claim", {})
    if claim.get("status") != "ready":
        failures.append({"id": "completion-claim", "reason": "completion_claim.status must be ready"})
    mode = evidence.get("mode")
    mode_rank = {"vanilla": 0, "mode-1-lean": 1, "mode-2-routed": 2, "mode-3-assured": 3, "full": 4}.get(mode, -1)
    if mode_rank >= 3:
        if impact_map is None:
            candidate = HERE / "impact-map.json"
            impact_map = load(candidate) if candidate.is_file() else None
        required_sections = {"definitions", "consumers", "tests", "compatibility", "documentation", "observability"}
        sections = (impact_map or {}).get("sections", {})
        for section in sorted(required_sections):
            row = sections.get(section)
            if not row:
                failures.append({"id": f"impact-map:{section}", "reason": "required impact section missing"})
            elif row.get("status") == "verified" and not row.get("evidence"):
                failures.append({"id": f"impact-map:{section}", "reason": "verified impact section has no evidence"})
            elif row.get("status") == "not_applicable" and not str(row.get("reason", "")).strip():
                failures.append({"id": f"impact-map:{section}", "reason": "not_applicable impact section has no reason"})
            elif row.get("status") not in {"verified", "not_applicable"}:
                failures.append({"id": f"impact-map:{section}", "reason": "impact section is not complete"})

        adversarial = evidence.get("adversarial_verification", {})
        if adversarial.get("status") != "PASS" or not adversarial.get("threat_model"):
            failures.append({"id": "adversarial-verification", "reason": "Mode 3+ requires PASS and a non-empty threat model"})
        adversarial_runs = adversarial.get("verification_runs", [])
        if not adversarial_runs:
            failures.append({"id": "adversarial-verification", "reason": "no adversarial challenge command recorded"})
        for run in adversarial_runs:
            _verify_command_entry(run, "adversarial-verification", workspace, cache, failures, reexecute)

        if checkpoint is None:
            candidate = HERE / "checkpoint.json"
            checkpoint = load(candidate) if candidate.is_file() else None
        if handoff is None:
            candidate = HERE / "session-handoff.json"
            handoff = load(candidate) if candidate.is_file() else None
        continuity_required = bool((checkpoint or {}).get("required") or (handoff or {}).get("required"))
        if continuity_required:
            if not checkpoint or checkpoint.get("status") != "ready" or not checkpoint.get("evidence_refs") or not str(checkpoint.get("next_action", "")).strip():
                failures.append({"id": "durable-checkpoint", "reason": "required checkpoint is not ready, evidence-backed, and actionable"})
            if not handoff or handoff.get("status") != "ready" or not handoff.get("verified_state") or not str(handoff.get("next_action", "")).strip():
                failures.append({"id": "session-handoff", "reason": "required handoff is not ready, evidence-backed, and actionable"})
    # Spec-first controls apply when the mode decision carried spec-synthesis
    # (recorded in evidence capabilities) or a spec.json exists beside the gate.
    if spec is None:
        candidate = HERE / "spec.json"
        spec = load(candidate) if candidate.is_file() else None
    if spec_freeze is None:
        candidate = HERE / "spec-freeze.json"
        spec_freeze = load(candidate) if candidate.is_file() else None
    spec_required = spec is not None or "spec-synthesis" in (evidence.get("capabilities") or [])
    if spec_required:
        if spec is None:
            failures.append({"id": "spec-synthesis", "reason": "mode declares spec-synthesis but no spec.json was found"})
        else:
            _spec_first_checks(spec, spec_freeze, evidence, workspace, resolved_task, failures, cache, reexecute)

    if mode == "full":
        scope = evidence.get("scope_approval", {})
        if scope.get("status") != "approved" or not str(scope.get("approved_by", "")).strip():
            failures.append({"id": "scope-approval", "reason": "full mode requires recorded human scope approval"})
        verifier = evidence.get("independent_verification", {})
        if verifier.get("status") != "PASS" or not str(verifier.get("verifier_profile", "")).strip():
            failures.append({"id": "independent-verification", "reason": "full mode requires an independent PASS with verifier profile"})
    return {
        "schema_version": 2,
        "verdict": "PASS" if not failures else "FAIL",
        "requirements": len(ledger.get("requirements", [])),
        "reexecuted_commands": len(cache),
        "failures": failures,
        "warnings": warnings,
        "completion_allowed": not failures,
        "mode": evidence.get("mode"),
    }


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--impact-map", type=Path)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--handoff", type=Path)
    parser.add_argument("--task", type=Path, help="task file to verify task_sha256 against")
    parser.add_argument("--spec", type=Path, help="filled spec.json (defaults to spec.json beside the gate)")
    parser.add_argument("--spec-freeze", type=Path, help="freeze record written by spec_synthesis validate --freeze")
    parser.add_argument("--no-reexecute", action="store_true", help="skip subprocess re-execution (diagnostics only)")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate(
        load(args.ledger),
        load(args.evidence),
        args.workspace,
        load(args.baseline) if args.baseline else None,
        task_path=args.task,
        reexecute=not args.no_reexecute,
        impact_map=load(args.impact_map) if args.impact_map else None,
        checkpoint=load(args.checkpoint) if args.checkpoint else None,
        handoff=load(args.handoff) if args.handoff else None,
        spec=load(args.spec) if args.spec else None,
        spec_freeze=load(args.spec_freeze) if args.spec_freeze else None,
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    raise SystemExit(0 if result["completion_allowed"] else 1)


if __name__ == "__main__":
    main()
