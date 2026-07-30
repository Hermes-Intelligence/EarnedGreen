#!/usr/bin/env python3
"""Attack the frozen checks: can a DIFFERENT implementation pass all of them?

The vacuity gate proves each check discriminates against the pre-change code. It
cannot prove the suite is strong enough as a whole -- a check can be non-vacuous
and still leave the requirement wide open. That is the gap SpecBench measures and
the one PBT-Bench quantifies (agent-authored properties miss 17-58% of seeded
bugs). This module attacks it.

THE PROBLEM THE ORIGINAL DESIGN DID NOT SOLVE
The brief "write a WRONG implementation that passes the checks" needs somebody to
know it is wrong. In a benchmark a held-out oracle knows. In a user's repo on a
Tuesday, nothing does -- so an adversary "win" would be the adversary's own
unverifiable claim, and we would have replaced a check we cannot trust with an
agent's opinion we cannot trust either.

WHAT IS MECHANICAL INSTEAD: A DIVERGENCE WITNESS
The adversary must supply, along with its implementation, a `witness`: a small
program that observes behaviour. The harness then establishes, with no oracle and
no judgement:

    the frozen suite is GREEN on the adversary's implementation, AND
    the witness OBSERVABLY DIVERGES between that implementation and the
    candidate's

Then the suite provably cannot tell two behaviourally different programs apart,
and at most one of them can satisfy the requirement. That is a demonstrated hole,
not an accusation. We never claim to know which side is correct -- naming the
winner needs the requirement, and that is exactly what we hand a human.

Exit codes: 0 the checks survived | 1 a hole was demonstrated.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import check_authoring
import harness_checks
import necessity_probe

Responder = Callable[[str], str]

WITNESS_ROOT = "witness/"
WITNESS_TIMEOUT = 120


class AdversaryError(RuntimeError):
    """The attack could not be evaluated. Never downgraded to 'checks survived':
    an attack we failed to run is not an attack the checks defeated."""


def build_brief(task: str, suite: dict[str, Any], check_sources: dict[str, str],
                interface: dict[str, str] | list[str]) -> str:
    """Brief the adversary.

    `interface` MUST carry the CURRENT CONTENT of each writable file, not just
    its name. Observed live: given only filenames, the adversary rewrote the file
    from scratch, silently dropped an unrelated function, and the repo's own
    existing test caught it. The harness then reported "checks held" -- a real
    statement about a careless attack, and a false impression of a strong suite.
    An adversary that fails by accident teaches us nothing and inflates our
    confidence, which is the exact failure this whole program exists to prevent.
    """
    if isinstance(interface, list):  # legacy shape: names only, no content
        interface = {rel: "" for rel in interface}
    lines = [
        "You are attacking a frozen check suite. You are not implementing the task honestly.",
        "",
        "TASK (what the checks are supposed to guarantee)",
        task.strip(),
        "",
        "THE FROZEN CHECKS (you may not modify these; edits are rejected)",
    ]
    for check in suite.get("checks", []):
        lines.append(f"  {check.get('id')} [{check.get('kind')}] -> {check.get('requirement_ref')}")
    for rel, source in check_sources.items():
        lines += ["", f"--- {rel} ---", source]
    lines += [
        "",
        "FILES YOU MAY WRITE, WITH THEIR CURRENT CONTENT",
        "Whatever you return REPLACES these files whole. Keep everything you are not attacking:",
        "breaking unrelated behaviour just makes an existing test fail, which ends your attack",
        "for a reason that teaches nobody anything.",
    ]
    for rel, source in interface.items():
        lines += ["", f"--- {rel} ---", source if source else "(file is new or empty)"]
    lines += [
        "",
        "YOUR GOAL",
        "Write an implementation that PASSES every frozen check while NOT doing what the task says.",
        "Aim at what the checks forgot: unchecked inputs, boundaries, error paths, ordering,",
        "state left behind. Hard-coding the exact values the checks assert is a legitimate attack.",
        "",
        "YOU MUST ALSO SUPPLY A WITNESS",
        "A witness is a short program that OBSERVES behaviour and prints a deterministic result.",
        "It will be run against your implementation and against the real one; your attack only",
        "counts if their outputs DIFFER. The witness is how you prove the checks cannot tell your",
        "implementation apart from a correct one -- without it, your attack is only a claim.",
        "The witness must be deterministic: no clocks, no randomness, no network. It is executed",
        "twice on the same code and discarded if it disagrees with itself.",
        "",
        "OUTPUT FORMAT: one JSON object, no prose.",
        json.dumps({
            "files": {"src/module.py": "<full file content of your attacking implementation>"},
            "witness": {"witness/probe.py": "<program that prints observed behaviour>"},
            "witness_command": ["python", "witness/probe.py"],
            "violated_requirement": "REQ-...",
            "explanation": "which requirement your implementation breaks, and what the checks failed to pin",
        }, indent=2),
    ]
    return "\n".join(lines)


def parse_attack(text: str, suite: dict[str, Any], workspace: Path) -> dict[str, Any]:
    """Strict, and hostile to the obvious cheat: the adversary defeating the
    checks by editing the checks."""
    attack = _load_json(text)
    files = attack.get("files")
    witness = attack.get("witness")
    command = attack.get("witness_command")
    if not isinstance(files, dict) or not files:
        raise AdversaryError("adversary supplied no implementation files")
    if not isinstance(witness, dict) or not witness:
        raise AdversaryError("adversary supplied no witness: an attack without a divergence witness "
                             "is an unverifiable claim and is not counted")
    if not isinstance(command, list) or not command:
        raise AdversaryError("adversary supplied no witness_command")
    protected = necessity_probe.suite_owned_paths(suite, workspace)
    for rel in files:
        _validate_impl_path(rel, protected)
    for rel in witness:
        _validate_witness_path(rel)
    return {"files": files, "witness": witness, "witness_command": command,
            "violated_requirement": attack.get("violated_requirement"),
            "explanation": attack.get("explanation", "")}


def _load_json(text: str) -> dict[str, Any]:
    if not text or not text.strip():
        raise AdversaryError("adversary returned an empty response")
    body = text.strip()
    match = check_authoring._FENCE.search(body)
    if match:
        body = match.group(1).strip()
    else:
        start, end = body.find("{"), body.rfind("}")
        if start == -1 or end <= start:
            raise AdversaryError("adversary returned no JSON object")
        body = body[start:end + 1]
    try:
        loaded = json.loads(body)
    except json.JSONDecodeError as error:
        raise AdversaryError(f"adversary returned unparseable JSON: {error}") from error
    if not isinstance(loaded, dict):
        raise AdversaryError("adversary returned JSON that is not an object")
    return loaded


def _safe_relative(rel: str) -> Path:
    if not rel or rel != rel.strip():
        raise AdversaryError(f"adversary supplied a blank or padded path {rel!r}")
    if rel.replace("\\", "/") != rel:
        raise AdversaryError(f"adversary supplied a non-portable path {rel!r}: use forward slashes")
    pure = Path(rel)
    if pure.is_absolute() or ".." in pure.parts or any(part in {"", "."} for part in pure.parts):
        raise AdversaryError(f"adversary supplied an unsafe path {rel!r}")
    return pure


def _validate_impl_path(rel: str, protected: set[str]) -> None:
    """The whole exercise is void if the adversary can rewrite the checks it is
    being measured against, so that is a hard rejection rather than a low score."""
    _safe_relative(rel)
    normalized = rel.replace("\\", "/")
    if normalized in protected or normalized.startswith(check_authoring._CHECK_ROOT):
        raise AdversaryError(f"adversary tried to modify the frozen check {rel!r}: "
                             "the suite under attack is not part of the attack surface")
    if normalized.startswith(WITNESS_ROOT):
        raise AdversaryError(f"adversary put an implementation file under {WITNESS_ROOT!r}")


def _validate_witness_path(rel: str) -> None:
    _safe_relative(rel)
    if not rel.replace("\\", "/").startswith(WITNESS_ROOT):
        raise AdversaryError(f"witness file {rel!r} must live under {WITNESS_ROOT!r}")


def _materialize(mapping: dict[str, Any], workspace: Path) -> None:
    for rel, content in mapping.items():
        if not isinstance(content, str):
            raise AdversaryError(f"content for {rel!r} is not text")
        target = workspace / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content.encode("utf-8"))


def _copy(source: Path, destination: Path) -> Path:
    """Copy a workspace, skipping what must never be copied.

    `.agentic` is excluded for a load-bearing reason: the scratch directory lives
    inside it, so copying the workspace wholesale copies the destination into
    itself and recurses until Windows' path limit stops it. `node_modules` and
    friends are excluded because a real repo would make this unusably slow.
    """
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination,
                    ignore=shutil.ignore_patterns(*harness_checks._EXCLUDED_DIRS))
    return destination


def _run_witness(command: list[str], workspace: Path) -> tuple[int | None, str]:
    """Run the witness with the workspace importable.

    A witness invoked as a script gets its own directory on sys.path, not the
    workspace, so `from src import ...` would fail for reasons that have nothing
    to do with the implementation under test. Making the project importable is
    the harness's job; the adversary's job is only to observe behaviour.
    """
    code, out, err = harness_checks._run(command, workspace, extra_env={"PYTHONPATH": str(workspace)})
    return code, (out or "") + (err or "")


def attackable(suite: dict[str, Any]) -> dict[str, Any]:
    """The suite as an attack can meaningfully face it: BEHAVIOURAL checks only.

    A symbol sweep asks whether the implementer inspected the consumers of what
    it changed. That is a real check about a real agent's process, and it is
    meaningless against a hypothetical implementation nobody wrote in a workspace
    nobody worked in -- it fails every attack, for free, and turns every result
    into "checks held". Same lesson the necessity probe already learned.
    """
    checks = [check for check in suite.get("checks", [])
              if check.get("kind") in necessity_probe._BEHAVIOURAL_KINDS]
    return dict(suite, checks=checks)


def _install_checks(suite: dict[str, Any], source: Path, destination: Path) -> None:
    """Copy the frozen check scripts into the attack workspace.

    The baseline snapshot predates authoring, so the check files do not exist in
    it. Without this the attack fails on 'check script missing' every single
    time, the adversary can never win by construction, and the harness reports
    "your checks are strong" 100% of the time. A mechanism that always returns
    comfort is worse than no mechanism, because it is believed.
    """
    for rel in necessity_probe.suite_owned_paths(suite, source):
        origin = source / rel
        if not origin.is_file():
            raise AdversaryError(f"the frozen check script {rel!r} is missing from the workspace: "
                                 "the attack cannot be evaluated against checks that are not there")
        target = destination / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origin, target)


def review(attack: dict[str, Any], suite: dict[str, Any], baseline_dir: Path,
           candidate_dir: Path, scratch: Path) -> dict[str, Any]:
    """Run the attack. The adversary wins only on demonstrated divergence."""
    suite = attackable(suite)
    attack_ws = _copy(baseline_dir, scratch / "adversary")
    _install_checks(suite, candidate_dir, attack_ws)
    _materialize(attack["files"], attack_ws)
    _materialize(attack["witness"], attack_ws)
    report = harness_checks.run_suite(suite, attack_ws, baseline_dir=baseline_dir)
    suite_green = report["green"]

    result: dict[str, Any] = {
        "schema_version": 1,
        "suite_green_on_attack": suite_green,
        "violated_requirement": attack.get("violated_requirement"),
        "explanation": attack.get("explanation", ""),
        "failed_checks": list(report["failing_check_ids"]),
    }
    if not suite_green:
        result["verdict"] = "checks-held"
        result["reason"] = ("the frozen suite caught the attacking implementation: on this attack the "
                            "checks constrain the requirement")
        return result

    # The suite is green on an implementation the adversary says is wrong. That
    # is still only a claim until the witness makes the difference observable.
    candidate_ws = _copy(candidate_dir, scratch / "candidate")
    _materialize(attack["witness"], candidate_ws)
    command = harness_checks._portable_command(attack["witness_command"])

    candidate_code, candidate_out = _run_witness(command, candidate_ws)
    repeat_code, repeat_out = _run_witness(command, candidate_ws)
    if (candidate_code, candidate_out) != (repeat_code, repeat_out):
        result["verdict"] = "inconclusive"
        result["reason"] = ("the witness disagrees with itself on identical code, so any divergence it "
                            "reports is noise; a nondeterministic witness proves nothing")
        return result
    if candidate_code not in (0,):
        result["verdict"] = "inconclusive"
        result["reason"] = (f"the witness failed to run against the real implementation (exit {candidate_code}); "
                            "it observes nothing and cannot demonstrate a gap")
        result["witness_output_tail"] = candidate_out[-800:]
        return result

    attack_code, attack_out = _run_witness(command, attack_ws)
    diverges = (attack_code, attack_out) != (candidate_code, candidate_out)
    result["witness_diverges"] = diverges
    result["witness_candidate_tail"] = candidate_out[-800:]
    result["witness_attack_tail"] = attack_out[-800:]
    if diverges:
        result["verdict"] = "suite-defeated"
        result["reason"] = ("the frozen suite is green on two implementations that the witness shows behave "
                            "differently, so the suite cannot distinguish them and at most one satisfies the "
                            "requirement. Which one is correct is not decidable from the checks: a human, or "
                            "a held-out oracle, must say.")
    else:
        result["verdict"] = "no-divergence"
        result["reason"] = ("the suite is green on the attack, but the witness cannot tell the two "
                            "implementations apart: no gap was demonstrated")
    return result


def attack(brief: str, responder: Responder, suite: dict[str, Any], baseline_dir: Path,
           candidate_dir: Path, scratch: Path) -> dict[str, Any]:
    try:
        parsed = parse_attack(responder(brief), suite, candidate_dir)
    except AdversaryError as error:
        return {"schema_version": 1, "verdict": "inconclusive", "adversary_calls": 1,
                "reason": f"the attack could not be evaluated: {error}"}
    result = review(parsed, suite, baseline_dir, candidate_dir, scratch)
    result["adversary_calls"] = 1
    return result


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description="Adversarial review of a frozen check suite.")
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True, help="the workspace holding the real change")
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--brief", type=Path, help="write the adversary brief here")
    parser.add_argument("--task")
    parser.add_argument("--response", type=Path, help="a recorded adversary response; no provider call is made")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    suite = json.loads(args.suite.read_text(encoding="utf-8-sig"))
    if args.response is None:
        if not (args.brief and args.task):
            parser.error("--brief and --task are required when building a brief")
        sources = {}
        for check in suite.get("checks", []):
            script = check.get("script")
            path = args.candidate / script if script else None
            if path and path.is_file():
                sources[script] = path.read_text(encoding="utf-8-sig")
        interface = {}
        for rel in sorted(necessity_probe.changed_files(
                args.baseline, args.candidate,
                exclude=necessity_probe.suite_owned_paths(suite, args.candidate))):
            path = args.candidate / rel
            interface[rel] = path.read_text(encoding="utf-8-sig") if path.is_file() else ""
        args.brief.write_text(build_brief(args.task, suite, sources, interface), encoding="utf-8")
        print(f"brief written: {args.brief}\nNo provider call was made. Re-run with --response.")
        raise SystemExit(0)
    recorded = args.response.read_text(encoding="utf-8-sig")
    result = attack("", lambda _prompt: recorded, suite, args.baseline, args.candidate, args.scratch)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    raise SystemExit(1 if result["verdict"] == "suite-defeated" else 0)


if __name__ == "__main__":
    main()
