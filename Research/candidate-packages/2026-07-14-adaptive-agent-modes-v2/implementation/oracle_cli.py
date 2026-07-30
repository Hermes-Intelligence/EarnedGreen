#!/usr/bin/env python3
"""The user-facing entry to the oracle stack: point it at YOUR repo, get pins.

Everything the measured pipeline needs, packaged for a person who cloned this
repository and wants oracles for their OWN code somewhere else on disk. The one
thing the user supplies — because observables are inherently per-repo — is a
CAPTURE command: any program that runs their code over their inputs and prints
one JSON object {"input_id": ["observable", "piece", ...], ...} to stdout.
ORACLE-GUIDE.md shows how to write one in a few lines. Everything else here is
the measured machinery, unchanged.

  derive   before/after git refs -> discriminating predicates (layer 1)
           materializes each ref in a THROWAWAY git worktree of the user's
           repo (read-only history access; the worktree is removed after),
           runs the capture in each, admits only predicates that are
           red-on-before, green-on-after and green on every --valid-ref
  guards   the current working tree -> preservation pins + findings (layer 2,
           deployable today): captures TWICE (determinism), pins the stream
           of every input the code handles now, reports crashes/instability
           as findings instead of pinning them
  evaluate pins vs any working tree -> green/red per predicate

The emitted pins are SELF-DESCRIBING (they carry the capture command), so the
harness `derived` check kind and the campaign runner consume them as-is.
Zero provider calls anywhere in this file.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import diff_oracle

CAPTURE_TIMEOUT = 300


def _run(command: list[str], cwd: Path, timeout: int = CAPTURE_TIMEOUT) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


def capture(command: list[str], cwd: Path) -> dict:
    resolved = [sys.executable if part == "{python}" else part for part in command]
    completed = _run(resolved, cwd)
    if completed.returncode != 0:
        raise SystemExit(f"capture command exited {completed.returncode} in {cwd}:\n{completed.stderr[-800:]}")
    try:
        streams = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise SystemExit(f"capture output is not a JSON object of streams: {error}\n"
                         f"stdout head: {completed.stdout[:300]!r}")
    if not isinstance(streams, dict) or not streams:
        raise SystemExit("capture printed no streams: expected {\"input_id\": [\"piece\", ...], ...}")
    return streams


class Worktree:
    """A throwaway checkout of one ref of the USER'S repo. History is read-only;
    the worktree registration is removed on exit, whatever happens."""

    def __init__(self, repo: Path, ref: str):
        self.repo, self.ref = repo, ref
        self.path: Path | None = None

    def __enter__(self) -> Path:
        self.path = Path(tempfile.mkdtemp(prefix="oracle-worktree-"))
        # mkdtemp created the dir; git worktree add wants to create it itself
        self.path.rmdir()
        completed = _run(["git", "worktree", "add", "--detach", str(self.path), self.ref], self.repo, 120)
        if completed.returncode != 0:
            raise SystemExit(f"git worktree add {self.ref} failed: {completed.stderr[-400:]}")
        return self.path

    def __exit__(self, *_exc) -> None:
        if self.path is not None:
            _run(["git", "worktree", "remove", "--force", str(self.path)], self.repo, 120)
            shutil.rmtree(self.path, ignore_errors=True)


def cmd_derive(args) -> None:
    repo = args.repo.resolve()
    with Worktree(repo, args.before_ref) as before_ws:
        before = capture(args.capture, before_ws)
    with Worktree(repo, args.after_ref) as after_ws:
        after = capture(args.capture, after_ws)
    variants = []
    for ref in args.valid_ref or []:
        with Worktree(repo, ref) as variant_ws:
            variants.append(capture(args.capture, variant_ws))
    derived = diff_oracle.derive(before, after, variants)
    predicates = list(derived["admitted"])
    relational_admitted = 0
    if args.relational:
        relational = diff_oracle.derive_relational(before, after, variants)
        predicates.extend(relational["admitted"])
        relational_admitted = len(relational["admitted"])
    pins = {
        "schema_version": 1,
        "role": f"diff-derived predicates for {repo.name} {args.before_ref}..{args.after_ref}",
        "capture_command": args.capture,
        "predicates": predicates,
        "valid_variant_refs": args.valid_ref or [],
        "rejected_format_pinning": derived["rejected_format_pinning"],
        "warning": ("with no --valid-ref, nothing filters predicates that pin incidental formatting; "
                    "measured guidance: give at least one different-but-valid ref whenever history has one"
                    if not args.valid_ref else None),
    }
    args.output.write_text(json.dumps(pins, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"admitted": len(derived["admitted"]),
                      "relational_admitted": relational_admitted,
                      "rejected_format_pinning": derived["rejected_format_pinning"],
                      "driver_errors": len(derived["driver_errors"]),
                      "written": str(args.output)}, indent=2))


def cmd_guards(args) -> None:
    tree = args.tree.resolve()
    first = capture(args.capture, tree)
    second = capture(args.capture, tree)
    pins, findings = [], []
    for input_id in sorted(first):
        stream = first[input_id]
        if not isinstance(stream, list):
            findings.append({"kind": "totality", "input_id": input_id,
                             "suspicion": f"the capture reported an error for this input: {stream!r:.160}"})
            continue
        if second.get(input_id) != stream:
            findings.append({"kind": "determinism", "input_id": input_id,
                             "suspicion": "two identical runs emitted different streams"})
            continue
        pins.append({"id": f"{input_id}::guard-seq", "input_id": input_id,
                     "projection": "seq", "expected": stream})
    out = {
        "schema_version": 1,
        "role": f"preservation guards for {tree.name}: the measured envelope, pinned forward "
                "(never demands more than the code already does)",
        "capture_command": args.capture,
        "predicates": pins,
        "findings": findings,
    }
    args.output.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"pins": len(pins), "findings": findings}, ensure_ascii=False, indent=2))


def cmd_evaluate(args) -> None:
    pins = json.loads(args.pins.read_text(encoding="utf-8-sig"))
    streams = capture(pins["capture_command"], args.tree.resolve())
    outcome = diff_oracle.evaluate(pins["predicates"], streams)
    print(json.dumps({"green": outcome["green"], "red": outcome["red_predicate_ids"],
                      "errors": outcome["errors"]}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if outcome["green"] else 1)


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="action", required=True)

    derive = sub.add_parser("derive", help="before/after refs of YOUR repo -> discriminating pins")
    derive.add_argument("--repo", type=Path, required=True)
    derive.add_argument("--before-ref", required=True)
    derive.add_argument("--after-ref", required=True)
    derive.add_argument("--valid-ref", action="append",
                        help="additional KNOWN-VALID refs (over-constraint filter); repeatable")
    derive.add_argument("--relational", action="store_true",
                        help="also derive gen-4 relational predicates (gained-kinds subset + per-kind "
                             "count-direction): partial-credit mid-levels for wide changes, validated "
                             "exploratory on the era material (evidence/gen4-era-validation-*.json)")
    derive.add_argument("--capture", nargs=argparse.REMAINDER, required=True,
                        help="everything after --capture is the command; use {python} for the interpreter")
    derive.add_argument("--output", type=Path, required=True)
    derive.set_defaults(func=cmd_derive)

    guards = sub.add_parser("guards", help="current tree -> preservation pins + findings")
    guards.add_argument("--tree", type=Path, required=True)
    guards.add_argument("--capture", nargs=argparse.REMAINDER, required=True)
    guards.add_argument("--output", type=Path, required=True)
    guards.set_defaults(func=cmd_guards)

    evaluate = sub.add_parser("evaluate", help="pins vs any tree -> green/red")
    evaluate.add_argument("--pins", type=Path, required=True)
    evaluate.add_argument("--tree", type=Path, required=True)
    evaluate.set_defaults(func=cmd_evaluate)

    args = parser.parse_args()
    for attribute in ("capture",):
        if hasattr(args, attribute):
            value = getattr(args, attribute)
            if value and value[0] == "--":
                setattr(args, attribute, value[1:])
    args.func(args)


if __name__ == "__main__":
    main()
