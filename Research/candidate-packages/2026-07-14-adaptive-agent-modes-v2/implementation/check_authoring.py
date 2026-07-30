#!/usr/bin/env python3
"""Author the check suite with a clean-context subagent, then admit it.

This is the half of the mechanism that removes hand-written `harness-checks.json`.
The loop is worth exactly the quality of its checks, so the checks must come from
somewhere for a repo the harness has never seen. They come from a subagent, and
they are trusted for exactly nothing: every proposed check must survive the
vacuity gate (`check_admission.py`) against the pre-change baseline before it is
allowed to become evidence.

Two things make the subagent worth its cost here, per F-2026-07-12-018:

  * CLEAN CONTEXT. The author has not read the implementer's reasoning, so it
    cannot inherit the implementer's assumptions about what "done" means. This is
    the one job where a fresh context is the product, not an overhead.
  * IT CANNOT GRADE ITSELF. Whatever it returns is run against code where the
    feature does not exist yet. A check that passes there is discarded, whatever
    the author claims about it.

Provider calls are injected, never made here: `author()` takes a `responder`
callable. That keeps this module fully testable at zero spend, and keeps spend
accounting in the campaign runner where the approval ceiling lives.

Exit codes: 0 suite authored and fully admitted | 1 otherwise.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import check_admission
import harness_checks
import project_detect

# A responder maps a brief to the subagent's raw text response.
Responder = Callable[[str], str]

# F-2026-07-12-014: 3-5 agents is where the returns stop. Authoring gets three:
# author, one re-author round, and the adversary (spent by check_adversary.py).
MAX_AUTHOR_CALLS = 2

_CHECK_ROOT = "checks/"
_ALLOWED_KINDS = {"acceptance", "differential", "property"}
_FENCE = re.compile(r"```(?:json)?\s*(.+?)```", re.S)


class AuthoringError(RuntimeError):
    """The subagent's response could not be used. Never silently tolerated:
    a malformed proposal that we 'repair' is a proposal we authored ourselves."""


def build_brief(task: str, root: Path, ledger: dict[str, Any],
                detected: dict[str, Any], uncovered_only: bool = True,
                existing_suite: dict[str, Any] | None = None,
                delivery: str | None = None) -> str:
    """The author's brief. Deliberately states the falsification rule up front:
    the author is told exactly how its work will be destroyed, which is the only
    honest way to ask for checks that discriminate.

    `delivery` replaces the default "return one JSON object" instruction for
    callers that collect the proposal another way (the campaign runner gives the
    author a real workspace and reads the files back out of it). It REPLACES
    rather than appends: two output contracts in one prompt is an instruction the
    author has to choose between, and whatever it chose we would call the result.
    """
    requirements = ledger.get("requirements", [])
    if uncovered_only and existing_suite:
        covered = {row.get("requirement_ref") for row in existing_suite.get("checks", [])}
        requirements = [row for row in requirements if row.get("id") not in covered]
    lines = [
        "You are authoring the check suite for a task you will not implement.",
        "",
        "TASK",
        task.strip(),
        "",
        f"REPOSITORY ROOT: {root}",
        f"TEST COMMAND (detected): {' '.join(project_detect.test_command(detected))}",
        f"TEST DIRECTORY: {detected.get('test_dir')}",
        "",
        "REQUIREMENTS THAT NEED CHECKS",
    ]
    for row in requirements:
        lines.append(f"  {row.get('id')}: {row.get('statement', row.get('text', ''))}")
    if not requirements:
        # No compiled ledger (a bare loop arm, or a real repo before any
        # objective compilation). The requirements still exist -- they live in
        # the task and in whatever the repo documents about itself. Saying so is
        # honest; leaving the section empty would read as "there are none".
        lines += [
            "  (No requirement ledger was compiled for this run.)",
            "  Derive the requirements yourself from the TASK above and from whatever this repository",
            "  documents about how its code must behave. Give each one a stable id of your own",
            "  (REQ-1, REQ-2, ...) and name it in `requirement_ref`.",
        ]
    lines += [
        "",
        "HOW YOUR WORK WILL BE JUDGED (read this before writing anything)",
        "Every check you propose is run against the code as it exists NOW, before the task is done.",
        "  - A check you mark `red-before-green-after` MUST FAIL now. If it passes now, it proves",
        "    nothing about the task and is DISCARDED.",
        "  - It must fail via an ASSERTION, not an ImportError. A check that fails only because a",
        "    symbol does not exist goes green the moment an empty stub exists. Import inside the test",
        "    and assert on behaviour, so that the assertion is what fails.",
        "  - A check you mark `green-before-green-after` MUST PASS now (it guards existing behaviour).",
        "Every check must name a `requirement_ref` from the list above.",
        "",
        f"HOW YOUR SCRIPT WILL BE EXECUTED: {_invocation_example(detected)}",
        "It is run on its own, from the repository root, NOT through the repo's own test files.",
        "It must therefore be a standalone program: import what it needs and exit non-zero on failure.",
        "",
    ]
    lines.append(delivery if delivery is not None else _DEFAULT_DELIVERY)
    return "\n".join(lines)


def _invocation_example(detected: dict[str, Any]) -> str:
    """Show the author the literal command, so it never has to guess."""
    for sample in ("checks/example_check.py", "checks/example_check.mjs"):
        try:
            return " ".join(project_detect.check_command(detected, sample))
        except project_detect.UnrunnableCheck:
            continue
    return "(no invocation could be determined for this stack)"


_DEFAULT_DELIVERY = "\n".join([
    "OUTPUT FORMAT: one JSON object, no prose.",
    json.dumps({
        "checks": [{
            "id": "kebab-case-id",
            "kind": "acceptance",
            "script": "checks/test_something.py",
            "requirement_ref": "REQ-...",
            "expectation": "red-before-green-after",
            "guidance": "shown to the implementer only when this check FAILS",
        }],
        "files": {"checks/test_something.py": "<full file content>"},
    }, indent=2),
    "",
    "Every `script` must appear as a key in `files`, must live under `checks/`, and must be",
    "runnable by the invocation shown above. Write the fewest checks that pin the requirements.",
])


def parse_proposal(text: str) -> dict[str, Any]:
    """Strict. A response we have to guess at is a response we wrote ourselves."""
    if not text or not text.strip():
        raise AuthoringError("author returned an empty response")
    body = text.strip()
    match = _FENCE.search(body)
    if match:
        body = match.group(1).strip()
    else:
        start, end = body.find("{"), body.rfind("}")
        if start == -1 or end <= start:
            raise AuthoringError("author returned no JSON object")
        body = body[start:end + 1]
    try:
        proposal = json.loads(body)
    except json.JSONDecodeError as error:
        raise AuthoringError(f"author returned unparseable JSON: {error}") from error
    if not isinstance(proposal, dict):
        raise AuthoringError("author returned JSON that is not an object")
    checks = proposal.get("checks")
    files = proposal.get("files")
    if not isinstance(checks, list) or not checks:
        raise AuthoringError("author proposed no checks")
    if not isinstance(files, dict):
        raise AuthoringError("author supplied no `files` map")
    for check in checks:
        if not isinstance(check, dict):
            raise AuthoringError("a proposed check is not an object")
        for field in ("id", "kind", "script", "requirement_ref", "expectation"):
            if not str(check.get(field, "")).strip():
                raise AuthoringError(f"proposed check is missing `{field}`: {check!r}")
        if check["kind"] not in _ALLOWED_KINDS:
            raise AuthoringError(f"check {check['id']!r} declares unsupported kind {check['kind']!r}")
        if check["script"] not in files:
            raise AuthoringError(f"check {check['id']!r} names script {check['script']!r} "
                                 "that the author did not supply in `files`")
    ids = [check["id"] for check in checks]
    if len(set(ids)) != len(ids):
        raise AuthoringError("proposed checks contain duplicate ids")
    for rel in files:
        _validate_path(rel)
    return {"checks": checks, "files": files}


def _validate_path(rel: str) -> None:
    """The harness EXECUTES these files. A model-supplied path is untrusted input:
    confine it to `checks/` so a proposal can never write over the implementation
    it is supposed to be judging, or anywhere outside the workspace at all."""
    if rel != rel.strip() or not rel:
        raise AuthoringError(f"author supplied a blank or padded path {rel!r}")
    normalized = rel.replace("\\", "/")
    if not normalized.startswith(_CHECK_ROOT):
        raise AuthoringError(f"author supplied {rel!r}: check files must live under {_CHECK_ROOT!r}")
    if normalized != rel:
        raise AuthoringError(f"author supplied a non-portable path {rel!r}: use forward slashes")
    pure = Path(normalized)
    if pure.is_absolute() or ".." in pure.parts or any(part in {"", "."} for part in pure.parts):
        raise AuthoringError(f"author supplied an unsafe path {rel!r}")


def materialize(proposal: dict[str, Any], workspace: Path) -> list[str]:
    """Write the author's check files into a workspace. Paths are re-validated
    here: `materialize` is reachable from a proposal loaded off disk, and a
    guard that only runs on one code path is not a guard."""
    written: list[str] = []
    for rel, content in proposal["files"].items():
        _validate_path(rel)
        if not isinstance(content, str):
            raise AuthoringError(f"content for {rel!r} is not text")
        target = workspace / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        # write_bytes, not write_text: text mode rewrites \n as \r\n on Windows,
        # so the file on disk would never match the sha `_pin` computed from the
        # string, and every authored check would fail closed as "modified after
        # freeze". The pinned bytes and the written bytes must be the same bytes.
        target.write_bytes(content.encode("utf-8"))
        written.append(rel)
    return written


def runnable(check: dict[str, Any], detected: dict[str, Any]) -> dict[str, Any]:
    """Compile an authored check into one the harness can actually execute.

    The author names a `script`; the suite runs a `command`. Deriving that
    command from the DETECTED stack is the whole point: a check compiled against
    a runner the repo does not use finds no tests, exits 0, and is green forever.
    That exact defect (a hardcoded `unittest` on a pytest repo) already shipped
    once in this package, so the runner is never assumed here.
    """
    if not project_detect.test_command(detected):
        raise AuthoringError("no test command was detected for this repository: a check suite compiled "
                             "without a runner would pass vacuously")
    try:
        command = project_detect.check_command(detected, check["script"])
    except project_detect.UnrunnableCheck as error:
        raise AuthoringError(str(error)) from error
    compiled = dict(check)
    compiled["command"] = harness_checks._portable_command(command)
    return compiled


def _pin(files: dict[str, str], scripts: list[str]) -> list[dict[str, str]]:
    """sha256 over exactly the bytes `materialize` writes, so a check script
    edited after the freeze fails closed rather than quietly grading the work."""
    return [{"path": rel, "sha256": hashlib.sha256(files[rel].encode("utf-8")).hexdigest().upper()}
            for rel in sorted(set(scripts))]


def _scratch_baseline(baseline_dir: Path, scratch: Path) -> Path:
    """Admission runs the proposed checks against pre-change code. The check
    files must exist there to run at all, so admission happens on a COPY: the
    baseline snapshot stays exactly what it claims to be."""
    if scratch.exists():
        shutil.rmtree(scratch)
    shutil.copytree(baseline_dir, scratch)
    return scratch


def _rejection_feedback(result: dict[str, Any]) -> str:
    """Guidance attaches to what failed (F-2026-07-12-016): the author is told
    which checks died and why, not lectured again about checks in general."""
    lines = ["Your proposal was run against the pre-change code. These checks were not admitted.",
             "Rewrite ONLY these; the admitted ones are already frozen and must not be resubmitted.", ""]
    for row in result["rejected"] + result["suspicious"]:
        lines.append(f"  {row['id']} [{row['verdict']}]: {row['reason']}")
    lines += ["", "Return the same JSON format, containing only the rewritten checks and their files."]
    return "\n".join(lines)


def author(brief: str, responder: Responder, baseline_dir: Path, scratch: Path,
           detected: dict[str, Any], ledger: dict[str, Any] | None = None,
           max_calls: int = MAX_AUTHOR_CALLS) -> dict[str, Any]:
    """Author checks, admit them, and re-author the rejects once.

    Only admitted checks survive. If the author burns its rounds without a clean
    suite, this returns what was admitted and reports the shortfall: a partial
    suite that the gate knows is partial beats a full suite that lies.
    """
    admitted: list[dict[str, Any]] = []
    files: dict[str, str] = {}
    rounds: list[dict[str, Any]] = []
    calls = 0
    prompt = brief
    while calls < max_calls:
        calls += 1
        try:
            proposal = parse_proposal(responder(prompt))
        except AuthoringError as error:
            rounds.append({"round": calls, "error": str(error), "admitted": 0})
            break
        workspace = _scratch_baseline(baseline_dir, scratch)
        materialize(proposal, workspace)
        try:
            compiled = [runnable(check, detected) for check in proposal["checks"]]
        except AuthoringError as error:
            rounds.append({"round": calls, "error": str(error), "admitted": 0})
            break
        result = check_admission.admit(compiled, workspace)
        by_id = {check["id"]: check for check in compiled}
        round_admitted = [by_id[row["id"]] for row in result["checks"] if row["verdict"] == "admitted"]
        for check in round_admitted:
            admitted.append(check)
            files[check["script"]] = proposal["files"][check["script"]]
        # Carry the shared helpers too (files under checks/ that are no check's
        # script): the admitted checks IMPORT them, so a suite without them is a
        # suite that cannot run. Frozen from the first admitting round (setdefault)
        # so a later re-author cannot silently swap a helper the earlier checks
        # were admitted against.
        if round_admitted:
            round_scripts = {check["script"] for check in proposal["checks"]}
            for rel, content in proposal["files"].items():
                if rel not in round_scripts:
                    files.setdefault(rel, content)
        rounds.append({"round": calls, "proposed": result["proposed"],
                       "admitted": len(round_admitted),
                       "rejected": [row["id"] for row in result["rejected"]],
                       "suspicious": [row["id"] for row in result["suspicious"]]})
        if not result["rejected"] and not result["suspicious"]:
            break
        prompt = _rejection_feedback(result)
    coverage = None
    if ledger is not None:
        coverage = check_admission.requirement_coverage(
            [{"requirement_ref": check["requirement_ref"]} for check in admitted], ledger)
    return {
        "schema_version": 1,
        "verdict": "PASS" if admitted and (coverage is None or coverage["complete"]) else "FAIL",
        "author_calls": calls,
        "rounds": rounds,
        "checks": admitted,
        "files": files,
        "requirement_coverage": coverage,
        "rule": ("only checks that failed on the pre-change code via an assertion are admitted; "
                 "an unadmitted check never becomes evidence"),
    }


def to_suite(result: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Freeze the admitted checks into a harness-authored suite.

    `authored_by: harness` is not a lie about who typed the check: it records
    that the HARNESS admitted it, which is what the freeze digest protects. The
    implementer may add checks; it may never weaken these.
    """
    files = result["files"]
    aux = _auxiliary_files(result)
    checks = [dict(check, authored_by="harness", files=_pin(files, [check["script"], *aux]))
              for check in result["checks"]]
    suite = {"schema_version": 1, "config": config or {}, "checks": checks}
    suite["harness_freeze_sha256"] = harness_checks.harness_freeze_sha256(suite)
    return suite


def _auxiliary_files(result: dict[str, Any]) -> list[str]:
    """Shared helper files: everything in `files` that is no check's own script.

    Pinned into EVERY check's integrity list, because they are shared imports:
    swapping one silently changes what several admitted checks actually test, and
    the freeze exists precisely to make that fail closed."""
    scripts = {check["script"] for check in result["checks"]}
    return sorted(rel for rel in result["files"] if rel not in scripts)


def merge(suite: dict[str, Any], result: dict[str, Any], detected: dict[str, Any]) -> dict[str, Any]:
    """Add admitted checks to an existing frozen suite and re-freeze.

    The compiled suite already carries the repo's own tests and the symbol sweep;
    authoring only ever ADDS. An authored id that collides with an existing one
    is an error rather than an overwrite: silently replacing a harness check with
    an agent-authored one is exactly the weakening the freeze exists to prevent.
    """
    merged = json.loads(json.dumps(suite))
    existing = {check.get("id") for check in merged.get("checks", [])}
    aux = _auxiliary_files(result)
    for check in result["checks"]:
        if check["id"] in existing:
            raise AuthoringError(f"authored check {check['id']!r} collides with a check already in the "
                                 "frozen suite: authoring may add checks, never replace them")
        compiled = runnable(check, detected)
        compiled["authored_by"] = "harness"
        compiled["files"] = _pin(result["files"], [check["script"], *aux])
        merged.setdefault("checks", []).append(compiled)
    merged["harness_freeze_sha256"] = harness_checks.harness_freeze_sha256(merged)
    return merged


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description="Author and admit a check suite (offline modes only).")
    parser.add_argument("--brief", type=Path, required=True, help="write/read the author brief here")
    parser.add_argument("--task", help="task statement (required to build a brief)")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--detected", type=Path, help="project_detect output")
    parser.add_argument("--response", type=Path,
                        help="a recorded author response; with this, no provider call is made")
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--scratch", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    ledger = json.loads(args.ledger.read_text(encoding="utf-8-sig")) if args.ledger else {"requirements": []}
    detected = json.loads(args.detected.read_text(encoding="utf-8-sig")) if args.detected else {}
    if args.response is None:
        if not args.task:
            parser.error("--task is required when building a brief")
        args.brief.write_text(build_brief(args.task, args.root, ledger, detected), encoding="utf-8")
        print(f"brief written: {args.brief}\n"
              "No provider call was made. Obtain a response, then re-run with --response.")
        raise SystemExit(0)
    if not args.baseline:
        parser.error("--baseline is required to admit a response")
    recorded = args.response.read_text(encoding="utf-8-sig")
    scratch = args.scratch or (args.baseline.parent / "author-scratch")
    result = author(args.brief.read_text(encoding="utf-8-sig") if args.brief.is_file() else "",
                    lambda _prompt: recorded, args.baseline, scratch, detected, ledger, max_calls=1)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    raise SystemExit(0 if result["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
