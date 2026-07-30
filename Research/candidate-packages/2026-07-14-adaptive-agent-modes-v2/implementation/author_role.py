#!/usr/bin/env python3
"""The AUTHOR role: a clean-context provider call that writes the loop's checks.

WHY THIS EXISTS. A campaign was halted at 4 of 28 approved calls because the
loop arm's frozen suite was `[symbol-sweep, public-tests]` -- nothing in it could
fail on anything the task is graded on. The loop arm was vanilla plus a symbol
sweep. The cause was structural: `compile_check_suite` can only compile checks
that already exist, so it works on medi-ny (which ships a hand-written
`harness/harness-checks.json`) and produces nothing on a fixture that does not.

Hand-writing the checks per fixture is not an option: it is the exact thing this
whole programme exists to remove. If the environment's answer to "where do the
checks come from" is "a human wrote them for this repo", then the measured effect
is that human, not the environment.

So the checks come from a subagent, and they are trusted for NOTHING:

  author (1 provider call, clean context, pre-change workspace)
    -> check_admission: every proposed check runs against the PRISTINE baseline
       and is admitted only if it reddens there via an assertion
    -> merge into the host suite and freeze

WHAT THE AUTHOR'S WORKSPACE IS FOR. It gets a real, writable copy of the
pre-change code, so it can RUN the checks it writes instead of guessing. Its copy
is then thrown away and admission re-runs everything against the untouched
baseline: if the author "helpfully" implemented the feature to make its own check
pass, that edit does not survive, and the check is judged on the code as it
really is.

THE HARD STOP THAT MAKES THIS HONEST. If authoring admits no behavioural check,
the trial does NOT run. An arm that reaches the provider without the mechanism it
is supposed to be testing produces a number about something else, and that number
would be reported as if it were about the loop. See `AuthoringShortfall`.
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import check_authoring
import harness_checks
import notes_bank
import project_detect

REPLY_FILE = "author-reply.json"

# Behavioural kinds: a check that can actually fail on the work. `symbol-sweep`
# is excluded everywhere else for the same reason and is not authorable at all.
_BEHAVIOURAL_KINDS = {"acceptance", "differential", "property", "e2e"}

_DELIVERY = "\n".join([
    "HOW TO DELIVER YOUR WORK",
    "",
    f"1. Write each check script as a real file under `checks/` in this workspace.",
    "   Any shared helper module your checks import (a test harness, a mock) must ALSO live",
    "   under `checks/` and import by relative path. Only files under `checks/` are collected.",
    "2. RUN each one. You have the pre-change code here, so you can see for yourself whether",
    "   your check fails on it. A check you never ran is a guess.",
    f"3. Write `{REPLY_FILE}` at the workspace root: one JSON object, no prose.",
    "",
    json.dumps({
        "checks": [{
            "id": "kebab-case-id",
            "kind": "property",
            "script": "checks/example_check.py",
            "requirement_ref": "REQ-1",
            "expectation": "red-before-green-after",
            "guidance": "shown to the implementer only when this check FAILS: say what is broken and where the rule is documented",
        }],
    }, indent=2),
    "",
    "`kind` must be one of: acceptance, property, differential.",
    "The file content is read from the workspace, so do not inline it in the JSON.",
    "",
    "LET ASSERTION FAILURES PROPAGATE RAW. Do not catch an assertion to print a tidy message:",
    "the admission gate reads the runner's own failure vocabulary, and a caught-and-reprinted",
    "assertion is indistinguishable from a crash — it will be refused as suspicious.",
    "",
    "DO NOT MODIFY THE IMPLEMENTATION. You are not doing this task; you are pinning it.",
    "Your copy of the code is discarded, and every check you propose is re-run against the",
    "untouched pre-change code. A check that only passes because you changed the code will be",
    "judged on the code as it really is, and discarded.",
])


class AuthoringShortfall(RuntimeError):
    """Authoring produced no admitted behavioural check.

    Deliberately fatal to the trial. The tempting alternative -- run the arm
    anyway with whatever compiled -- is precisely the defect that wasted 4
    approved calls, and it fails silently: the run completes, gets a score, and
    the score is reported as the loop's.
    """


def build_brief(base_run: Path, task_text: str, detected: dict[str, Any],
                ledger: dict[str, Any] | None = None,
                notes: list[dict[str, Any]] | None = None) -> str:
    """Notes from the institutional bank land HERE — in the brief, at the moment
    they are relevant — because prose delivered anywhere else measured inert.
    They render ahead of the delivery contract so the author reads the lessons
    before deciding what to write, not after deciding how to hand it in."""
    delivery = _DELIVERY
    section = notes_bank.render_for_brief(notes or [])
    if section:
        delivery = section + "\n\n" + _DELIVERY
    return check_authoring.build_brief(
        task=task_text, root=Path("."), ledger=ledger or {"requirements": []},
        detected=detected, delivery=delivery)


def verify_pristine(workspace: Path, baseline_record: dict[str, Any]) -> None:
    """Refuse to treat a workspace as pre-change unless it verifiably IS.

    The author (and admission) must run against pre-change code. The pristine
    workspace is preferred over the host-baseline snapshot because the snapshot
    strips excluded directories -- and for a JS repo that strips `node_modules`,
    the very runtime the checks need, so every authored check dies on import at
    admission (error-red) and the arm is refused for an infrastructure reason
    (observed live 2026-07-19, 1 approved call lost). Using the workspace is
    only sound while nothing has touched it; this proves that instead of
    assuming it.
    """
    inventory = baseline_record.get("inventory") or {}
    current = {path.relative_to(workspace).as_posix(): harness_checks.sha256_bytes(path)
               for path in harness_checks._workspace_files(workspace)}
    if current != inventory:
        changed = sorted(set(current) ^ set(inventory))[:10]
        drifted = sorted(path for path in set(current) & set(inventory)
                         if current[path] != inventory[path])[:10]
        raise RuntimeError(
            "the workspace is no longer the pre-change state, so it cannot serve as the "
            f"authoring/admission baseline (added/removed: {changed}, modified: {drifted})")


def prepare_author_run(runs_root: Path, run_id: str, baseline_dir: Path, brief: str,
                       provider: str) -> Path:
    """A run directory the provider adapter can execute, holding pre-change code.

    `baseline_dir` should be the PRISTINE WORKSPACE (verified via
    verify_pristine), not the host-baseline snapshot: the snapshot strips
    `node_modules` and friends, and an author whose checks cannot import the
    code's runtime is forced to hand-roll mocks -- the exact weak-observable
    habit the notes bank warns against. The author must never see the
    implementer's work; pristineness is what guarantees there is none to see.
    """
    run = runs_root / run_id
    if run.exists():
        raise RuntimeError(f"author run directory already exists: {run}")
    workspace = run / "workspace"
    workspace.mkdir(parents=True)
    shutil.copytree(baseline_dir, workspace, dirs_exist_ok=True)
    (run / "prompt.txt").write_text(brief, encoding="utf-8")
    manifest = {
        "schema_version": 2,
        "status": "prepared-zero-provider",
        "role": "check-author",
        "run_id": run_id,
        "provider": provider,
        "workspace": "workspace",
        "provider_calls": 0,
        "prepared_at": datetime.now(timezone.utc).isoformat(),
        "prompt_sha256": harness_checks.sha256_bytes(run / "prompt.txt"),
        # The author is not graded and produces no solution. Saying so in the
        # manifest keeps a stray author run from ever being mistaken for a trial.
        "graded": False,
        "note": "clean-context check authoring; this workspace is discarded after the reply is read",
    }
    (run / "run-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return run


def collect_proposal(author_run: Path) -> str:
    """Read the author's reply and rebuild the proposal `check_authoring` expects.

    The author declares its checks in JSON and writes the scripts as real files;
    this reunites the two into the single object `parse_proposal` validates, so
    the campaign path and the offline path go through exactly the same checking.

    IT CAPTURES THE WHOLE `checks/` SUBTREE, not only the declared scripts. The
    first live author run proved why: a real author factors shared setup into
    helper modules (`_env.mjs`, a jspdf mock) that every check imports. Collecting
    only the declared `script` files dropped those helpers, so every check died on
    `ERR_MODULE_NOT_FOUND` at admission -- an error-red, never an assertion-red, so
    nothing was admitted and the trial was refused for a reason that was entirely
    my contract's fault, not the author's. With the helpers present, all six of
    that author's checks admit. A check's dependencies must travel with it.
    """
    workspace = author_run / "workspace"
    reply = workspace / REPLY_FILE
    if not reply.is_file():
        raise check_authoring.AuthoringError(
            f"the author wrote no {REPLY_FILE}: there is no proposal to admit")
    try:
        declared = json.loads(reply.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as error:
        raise check_authoring.AuthoringError(f"{REPLY_FILE} is not valid JSON: {error}") from error
    if not isinstance(declared, dict) or not isinstance(declared.get("checks"), list):
        raise check_authoring.AuthoringError(f"{REPLY_FILE} holds no `checks` array")

    # Every file the author wrote under checks/ — scripts AND their shared helpers.
    files: dict[str, str] = {}
    checks_dir = workspace / "checks"
    if checks_dir.is_dir():
        for path in sorted(p for p in checks_dir.rglob("*") if p.is_file()):
            rel = path.relative_to(workspace).as_posix()
            # Untrusted paths: confine to checks/ before reading (parse_proposal
            # re-validates, but a guard that runs on only one path is not a guard).
            check_authoring._validate_path(rel)
            files[rel] = path.read_text(encoding="utf-8-sig")

    for check in declared["checks"]:
        if not isinstance(check, dict):
            raise check_authoring.AuthoringError("a declared check is not an object")
        script = str(check.get("script", "")).strip()
        if not script:
            raise check_authoring.AuthoringError(f"a declared check names no `script`: {check!r}")
        check_authoring._validate_path(script)
        if script not in files:
            raise check_authoring.AuthoringError(
                f"check {check.get('id')!r} names {script!r}, which the author did not write under checks/")
    return json.dumps({"checks": declared["checks"], "files": files}, ensure_ascii=False)


def behavioural(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [check for check in checks if check.get("kind") in _BEHAVIOURAL_KINDS]


def author_into(suite: dict[str, Any], responder: Callable[[str], str], brief: str,
                baseline_dir: Path, scratch: Path, detected: dict[str, Any],
                ledger: dict[str, Any] | None = None,
                max_calls: int = 1) -> tuple[dict[str, Any], dict[str, Any]]:
    """Author, admit, and merge into `suite`. Returns (merged_suite, record).

    Raises AuthoringShortfall when nothing behavioural survived admission.
    """
    result = check_authoring.author(brief, responder, baseline_dir, scratch, detected,
                                    ledger=ledger, max_calls=max_calls)
    admitted = behavioural(result["checks"])
    if not admitted:
        raise AuthoringShortfall(
            "authoring admitted no behavioural check: every proposal was vacuous, error-red or "
            "unusable, so the arm holds no mechanism and the trial would measure something else. "
            f"rounds={json.dumps(result['rounds'], ensure_ascii=False)}")
    merged = check_authoring.merge(suite, dict(result, checks=admitted), detected)
    return merged, result


def install_checks(files: dict[str, str], workspace: Path) -> list[str]:
    """Write every admitted-suite file into a workspace, byte-for-byte.

    ALL of `files`: the check scripts AND the shared helpers they import. Installing
    only the declared scripts is exactly the bug the first live canary hit -- the
    helpers were left behind and every check broke on import in the solution
    workspace, the same way they had broken at admission.

    `write_bytes` via check_authoring.materialize, so the file on disk matches the
    sha the suite pinned. Text mode would rewrite \\n as \\r\\n here on Windows and
    every authored check would fail closed as "modified after freeze".
    """
    return check_authoring.materialize({"files": dict(files)}, workspace)


def detect_project(workspace: Path) -> dict[str, Any]:
    return project_detect.detect(workspace)


def _repo_root() -> Path:
    for parent in (HERE, *HERE.parents):
        if (parent / "Runtime/stable/manifest.json").exists():
            return parent
    raise RuntimeError("AgenticWorkBestPractices root not found")


def authoring_policy(fixture_id: str) -> dict[str, Any]:
    """Must this fixture's loop arm author its own checks?

    ONE truth, read by both the campaign constructor (which must reserve the
    calls) and the runner (which must spend them). Two sides deciding this
    independently is the defect that let a suite and its consumers agree with
    each other about a key that never existed.

    The trigger is deliberately NOT "does the fixture discriminate" -- that
    question can only be answered with the after-state, which is held-out oracle
    knowledge a real repository does not have. The trigger is "does this repo
    declare checks of its own", which any repo knows about itself.
    """
    import fixture_admission  # local: fixture_admission imports harness_checks at module scope

    fixture_dir, contract = fixture_admission.local_fixture_dir(fixture_id)
    if contract is None:
        fixture_dir = _repo_root() / "Evals/fixtures" / fixture_id
    declared = [str(path.relative_to(fixture_dir).as_posix())
                for path in (fixture_dir / "harness" / "harness-checks.json",
                             fixture_dir / "public" / "harness-checks.json")
                if path.is_file()]
    return {
        "enabled": not declared,
        "max_calls_per_trial": 0 if declared else 1,
        "declared_by": declared,
        "reason": (f"the repository declares its own checks ({', '.join(declared)}); authoring would "
                   "add nothing and would not be what a real repo does"
                   if declared else
                   "the repository declares no checks of its own, so the loop has nothing to run "
                   "until a clean-context author writes them and the vacuity gate admits them"),
    }
