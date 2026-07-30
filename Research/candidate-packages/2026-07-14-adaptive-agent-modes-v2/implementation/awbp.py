#!/usr/bin/env python3
"""awbp - the whole environment, from the repository you are in.

  awbp init                 once per repo: detect the stack, verify the tests run
                            today, write .agentic/project.json
  awbp task "<text>"        route it, snapshot the baseline, compile and freeze
                            the check suite
  awbp author               write the check-authoring brief for a clean-context
                            subagent (no provider call is made here)
  awbp admit <response>     admit the subagent's checks: only those that FAIL on
                            the pre-change code, via an assertion, are frozen in
  awbp check                run the frozen suite once (what the loop and the gate run)
  awbp probe                after green: is it EARNED? revert each hunk and demand
                            that some check notices
  awbp adversary [response] brief, then evaluate, an attack on the frozen checks
  awbp status               what this repo currently has
  awbp bootstrap --capture <cmd>  self-hardening suite for NEW work: relations at
                            birth (envelope + determinism), no history needed
  awbp accept --by <who>    freeze the current tree as the accepted floor; unmet
                            spec/council predicates are surfaced, never dropped
  awbp support --decision .. --options .. --risks .. --missing ..
                            budgeted council escalation; writes the two blind
                            briefs for your own strong subagents
  awbp council-admit <memo> validate the reconciled memo; admit its invariants
                            as predicates (prose is rejected by design)
  awbp review <dims> [--response <file>]
                            the T2 gate: named-unverified dimensions need a
                            recorded strong review before done (an approve must
                            carry predicates or an honest declaration)
  awbp calibrate --baseline <dir> --accepted <dir> [--hollow <dir>]
                            the full null/golden/adversarial triad over the
                            bootstrap suite; names decoration predicates
  awbp deny-rules [--paths] deterministic deny rules for protected paths (deny
                            resolves before the classifier; allow does not)

Python, not PowerShell, is the entry point on purpose: the same command has to
work in Claude on Windows and in Codex under WSL, and every step is Python
already. `awbp.ps1` is a thin shim over this file.

NOTHING here calls a model. Briefs go out, responses come back as files. In daily
use the agent driving the session IS the responder (it spawns the subagent
itself); in a benchmark the campaign runner is. That keeps spend where the
approval ceiling lives, and keeps this tool free to run.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

GREEN, YELLOW, RED, CYAN, DIM, OFF = "\033[32m", "\033[33m", "\033[31m", "\033[36m", "\033[2m", "\033[0m"


def _supports_colour() -> bool:
    return sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def say(text: str, colour: str = "") -> None:
    # flush: stdout is block-buffered whenever this is piped or captured -- which
    # is exactly how an agent reads it -- so without this our lines land AFTER a
    # subprocess's output and the narration describes the wrong step.
    if colour and _supports_colour():
        print(f"{colour}{text}{OFF}", flush=True)
    else:
        print(text, flush=True)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def dump(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_step(script: str, arguments: list[str]) -> int:
    return subprocess.run([sys.executable, str(HERE / script), *arguments]).returncode


class Context:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace.resolve()
        self.agentic = self.workspace / ".agentic"

    @property
    def project(self) -> Path:
        return self.agentic / "project.json"

    @property
    def suite(self) -> Path:
        return self.agentic / "check-suite.json"

    @property
    def baseline(self) -> Path:
        return self.agentic / "baseline-workspace"

    @property
    def ledger(self) -> Path:
        return self.agentic / "objective-ledger.json"

    @property
    def task_file(self) -> Path:
        return self.agentic / "task.md"

    def require(self, path: Path, hint: str) -> None:
        if not path.exists():
            say(f"Missing: {path.name}. {hint}", RED)
            raise SystemExit(2)


def cmd_init(context: Context, args: argparse.Namespace) -> int:
    say(f"Detecting the stack in {context.workspace} ...", CYAN)
    arguments = ["--workspace", str(context.workspace)]
    if args.no_verify:
        arguments.append("--no-verify")
    code = run_step("project_detect.py", arguments)
    if code != 0:
        say("\nNo test command could be identified, or the repo's tests are not green today.", YELLOW)
        say("The loop still gives you the symbol sweep and the completion gate, but acceptance", YELLOW)
        say("checks need a test command. Fix .agentic/project.json and re-run.", YELLOW)
        return code
    say('\nReady. Next:  awbp task "<what you want done>"', GREEN)
    return 0


def cmd_task(context: Context, args: argparse.Namespace) -> int:
    if not context.project.exists():
        say("This repository has not been initialised. Running init first ...", YELLOW)
        if run_step("project_detect.py", ["--workspace", str(context.workspace)]) != 0:
            return 1
    task_file = Path(args.task_file) if args.task_file else context.task_file
    if not args.task_file:
        if not args.text:
            say('Give the task:  awbp task "<text>"   (or --task-file <path>)', RED)
            return 2
        task_file.parent.mkdir(parents=True, exist_ok=True)
        task_file.write_text(" ".join(args.text), encoding="utf-8")
    say("Routing and preparing ...", CYAN)
    code = run_step("prepare_context.py", ["--task-file", str(task_file), "--workspace", str(context.workspace)])
    if code != 0:
        return code

    # WHERE DOES THE STATE LIVE? Asked at the START, because the answer stops
    # being cheap later. A task once scoped "local-first is fine and expected"
    # produced a polished TEAM board that stored the team's ideas in one person's
    # browser. The scope line was correct; nothing connected it to shippability,
    # and nobody noticed until the owner asked whether it worked in production.
    # "browser-only (demo)" is a fine answer — it just has to be CHOSEN.
    if args.state_lives_in:
        (context.agentic / "state.json").parent.mkdir(parents=True, exist_ok=True)
        (context.agentic / "state.json").write_text(
            json.dumps({"state_lives_in": args.state_lives_in}, indent=1) + "\n", encoding="utf-8")
        say(f"State recorded: {args.state_lives_in}", GREEN)
    else:
        say("\nIf this task creates or changes state a USER can see, answer this now:", YELLOW)
        say("  where does that state live in production, and who else can see it?")
        say("  awbp task ... --state-lives-in \"postgres, shared across the internal team\"")
        say("  --state-lives-in \"browser-only (demo)\" is a valid answer; defaulting into it is not.")

    say("\nPrepared. Next:", GREEN)
    say("  awbp author        write the check brief, then have a CLEAN-CONTEXT subagent answer it")
    say("  (or go straight to implementing if the repo's own tests already pin this task)")
    return 0


def cmd_author(context: Context, args: argparse.Namespace) -> int:
    """Emit the brief. No provider call: the caller decides who answers it."""
    import check_authoring

    context.require(context.project, 'Run:  awbp init')
    context.require(context.task_file, 'Run:  awbp task "<text>"')
    detected = load(context.project)
    ledger = load(context.ledger) if context.ledger.exists() else {"requirements": []}
    existing = load(context.suite) if context.suite.exists() else None
    brief = check_authoring.build_brief(
        context.task_file.read_text(encoding="utf-8-sig"), context.workspace, ledger, detected,
        existing_suite=existing)
    target = context.agentic / "author-brief.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(brief, encoding="utf-8")
    say(f"Brief written: {target}", GREEN)
    say("\nHave a subagent with a CLEAN CONTEXT answer it. Clean context is the point: an author")
    say("that has read your reasoning inherits your assumptions about what 'done' means.")
    say("Save its raw reply to a file, then:")
    say("  awbp admit <that file>")
    return 0


def cmd_admit(context: Context, args: argparse.Namespace) -> int:
    import check_authoring

    context.require(context.baseline, 'Run:  awbp task "<text>"  first (it snapshots the pre-change code)')
    detected = load(context.project)
    ledger = load(context.ledger) if context.ledger.exists() else {"requirements": []}
    response = Path(args.response).read_text(encoding="utf-8-sig")
    say("Running each proposed check against the PRE-CHANGE code ...", CYAN)
    result = check_authoring.author(
        "", lambda _prompt: response, context.baseline, context.agentic / "author-scratch",
        detected, ledger, max_calls=1)
    dump(context.agentic / "admission-report.json", result)

    round_one = result["rounds"][0] if result["rounds"] else {}
    if "error" in round_one:
        say(f"\nThe response could not be used: {round_one['error']}", RED)
        return 1
    say(f"\nadmitted {round_one.get('admitted', 0)} of {round_one.get('proposed', 0)} proposed checks", GREEN)
    for reason, colour in (("rejected", RED), ("suspicious", YELLOW)):
        for check_id in round_one.get(reason, []):
            say(f"  {reason}: {check_id}", colour)
    if not result["checks"]:
        say("\nNothing was admitted. A check that passes before the feature exists proves nothing.", YELLOW)
        say("Re-brief the author with .agentic/admission-report.json and try again.", YELLOW)
        return 1

    suite = load(context.suite) if context.suite.exists() else {"schema_version": 1, "config": {}, "checks": []}
    try:
        merged = check_authoring.merge(suite, result, detected)
    except check_authoring.AuthoringError as error:
        say(f"\n{error}", RED)
        return 1
    check_authoring.materialize(result, context.workspace)
    dump(context.suite, merged)
    say(f"\nFrozen into {context.suite.name}: {len(merged['checks'])} checks total.", GREEN)
    coverage = result.get("requirement_coverage")
    if coverage and not coverage["complete"]:
        say(f"Still uncovered: {', '.join(coverage['uncovered_requirement_ids'])}", YELLOW)
        say("Re-run  awbp author  to brief for those, or accept that they are unproven.", YELLOW)
    say("\nNext: implement, then  awbp check")
    return 0


def cmd_check(context: Context, args: argparse.Namespace) -> int:
    context.require(context.suite, 'No frozen check suite. Run:  awbp task "<text>"')
    code = subprocess.run([sys.executable, str(context.agentic / "verification_loop.py"), "step",
                           "--suite", str(context.suite), "--workspace", str(context.workspace)]).returncode
    if code == 0:
        say("GREEN - every independent check passes. Next: awbp probe", GREEN)
    elif code == 1:
        say("RED - fix the causes in .agentic/loop-feedback.json, then: awbp check", YELLOW)
    elif code == 2:
        say("STOPPED - iteration budget or no progress. Escalate to a human; do not weaken checks.", RED)
    else:
        say("Suite integrity failure - the frozen checks were modified.", RED)
    return code


def cmd_probe(context: Context, args: argparse.Namespace) -> int:
    context.require(context.baseline, 'No baseline snapshot. Run:  awbp task "<text>"')
    say("Reverting each hunk of your change to see whether any check notices ...", CYAN)
    code = run_step("necessity_probe.py", [
        "--suite", str(context.suite), "--baseline", str(context.baseline),
        "--workspace", str(context.workspace), "--output", str(context.agentic / "necessity-report.json")])
    if code == 0:
        say("EARNED - every substantive hunk is necessary for at least one check.", GREEN)
    else:
        say("NOT EARNED - some hunks are covered by no check (.agentic/necessity-report.json).", YELLOW)
        say("Each one is either unnecessary code or untested code. Add a check or remove it.", YELLOW)
    return code


def cmd_adversary(context: Context, args: argparse.Namespace) -> int:
    import check_adversary
    import necessity_probe

    context.require(context.suite, 'No frozen check suite. Run:  awbp task "<text>"')
    suite = load(context.suite)
    if not args.response:
        sources = {}
        for check in suite.get("checks", []):
            script = check.get("script")
            path = context.workspace / script if script else None
            if path and path.is_file():
                sources[script] = path.read_text(encoding="utf-8-sig")
        # The adversary gets each writable file's CURRENT CONTENT, not just its
        # name: given names only it rewrites from scratch, drops unrelated code,
        # and dies on an existing test -- which we would then misread as our
        # checks being strong.
        interface = {}
        for rel in sorted(necessity_probe.changed_files(
                context.baseline, context.workspace,
                exclude=necessity_probe.suite_owned_paths(suite, context.workspace))):
            path = context.workspace / rel
            interface[rel] = path.read_text(encoding="utf-8-sig") if path.is_file() else ""
        brief = check_adversary.build_brief(
            context.task_file.read_text(encoding="utf-8-sig"), suite, sources, interface)
        target = context.agentic / "adversary-brief.md"
        target.write_text(brief, encoding="utf-8")
        say(f"Brief written: {target}", GREEN)
        say("\nHave a subagent try to DEFEAT your checks. Save its raw reply, then:")
        say("  awbp adversary <that file>")
        return 0

    response = Path(args.response).read_text(encoding="utf-8-sig")
    say("Running the attack against the frozen checks ...", CYAN)
    result = check_adversary.attack("", lambda _prompt: response, suite, context.baseline,
                                    context.workspace, context.agentic / "adversary-scratch")
    dump(context.agentic / "adversary-report.json", result)
    verdict = result["verdict"]
    if verdict == "checks-held":
        say("\nCHECKS HELD - the frozen suite caught the attack.", GREEN)
        say(f"  caught by: {', '.join(result['failed_checks'])}", DIM)
        say("  Read that list before taking comfort in it: if the attack died on a check that has", DIM)
        say("  nothing to do with this task, it failed by accident and proves little.", DIM)
        return 0
    if verdict == "suite-defeated":
        say("\nSUITE DEFEATED - your checks are green on an implementation that provably behaves", RED)
        say("differently from yours. At most one of them is right, and the checks cannot tell.", RED)
        say(f"  {result['reason']}", DIM)
        say("Add a check that pins the difference, then re-run: awbp check", YELLOW)
        return 1
    if verdict == "no-divergence":
        say("\nNO HOLE DEMONSTRATED - the attack passes, but nothing observable separates it", YELLOW)
        say("from your implementation, so there is nothing to fix.", YELLOW)
        return 0
    say(f"\nINCONCLUSIVE - {result['reason']}", YELLOW)
    say("An attack that could not be run is not an attack your checks defeated.", DIM)
    return 0


def cmd_status(context: Context, args: argparse.Namespace) -> int:
    if not context.project.exists():
        say("not initialised - run:  awbp init", YELLOW)
        return 1
    import project_detect

    project = load(context.project)
    say(f"workspace     {context.workspace}")
    say(f"test command  {' '.join(project_detect.test_command(project)) or '(none detected)'}")
    say(f"evidence      {project_detect.test_evidence(project)}")
    if context.suite.exists():
        suite = load(context.suite)
        say(f"frozen suite  {len(suite.get('checks', []))} checks")
        for check in suite.get("checks", []):
            say(f"  {check.get('id')}  [{check.get('kind')}]", DIM)
    else:
        say('frozen suite  none - run:  awbp task "<text>"')
    return 0


def cmd_bootstrap(context: Context, args: argparse.Namespace) -> int:
    """`awbp bootstrap --capture <cmd...>`: start the self-hardening suite for
    NEW work — relations at birth (envelope + determinism), no history needed."""
    import oracle_bootstrap
    suite = oracle_bootstrap.BootstrapSuite(context.agentic / "bootstrap-suite.json")
    outcome = suite.relations_at_birth(context.workspace, args.capture)
    suite.save()
    say(f"pins added: {outcome['pins_added']}", GREEN)
    for finding in outcome["findings"]:
        say(f"FINDING {finding['kind']} on {finding['input_id']}", RED)
    say(f"suite: {context.agentic / 'bootstrap-suite.json'}", DIM)
    return 0 if not outcome["findings"] else 1


def cmd_accept(context: Context, args: argparse.Namespace) -> int:
    """`awbp accept --by <who>`: freeze the CURRENT tree as the accepted floor;
    spec/council/finding predicates are re-verified and unmet ones surfaced."""
    import oracle_bootstrap
    suite = oracle_bootstrap.BootstrapSuite(context.agentic / "bootstrap-suite.json")
    outcome = suite.freeze_acceptance(context.workspace, accepted_by=args.by)
    suite.save()
    say(f"frozen inputs: {outcome['frozen_inputs']}  verdict: {outcome['verdict']}",
        GREEN if outcome["verdict"] == "clean" else YELLOW)
    for unmet in outcome["unmet_predicates"]:
        say(f"UNMET: {unmet} — either the work is incomplete or the predicate is wrong; "
            "a person decides, nothing is dropped silently", YELLOW)
    return 0 if outcome["verdict"] == "clean" else 1


def cmd_support(context: Context, args: argparse.Namespace) -> int:
    """`awbp support --decision ... --options ... --risks ... --missing ...`:
    budgeted escalation request; on grant, the council briefs are written for
    the driving session to run with its own subagents."""
    import support_council
    import tiered_loop
    state = tiered_loop.TieredState(context.agentic / "tiered.json")
    brief = {"decision": args.decision, "options_considered": args.options,
             "risks": args.risks, "what_i_might_be_missing": args.missing}
    outcome = state.support(brief)
    state.save()
    if not outcome["granted"]:
        say(f"DENIED: {outcome['reason']}", RED)
        return 1
    task_context = {"brief": brief, "workspace": str(context.workspace)}
    for label, name in (("A", "council-brief-a.md"), ("B", "council-brief-b.md")):
        (context.agentic / name).write_text(
            support_council.draft_brief(task_context, label), encoding="utf-8")
    say(f"GRANTED (remaining: {outcome['remaining']}). Briefs written:", GREEN)
    say(f"  {context.agentic / 'council-brief-a.md'}  (strong model #1, blind)", DIM)
    say(f"  {context.agentic / 'council-brief-b.md'}  (strong model #2, blind)", DIM)
    say("Run each with a separate strong subagent, then continue the protocol with", DIM)
    say("support_council.cross_brief / memo_brief / countersign_brief; admit the memo's", DIM)
    say("invariants via oracle_bootstrap.admit_proposals(..., provenance='council').", DIM)
    return 0


def cmd_review(context: Context, args: argparse.Namespace) -> int:
    """`awbp review <dimensions...>` writes the T2 brief;
    `awbp review --response <file>` records the reply and reports whether done
    is unblocked. This is the tiered gate's user-facing half — without it the
    escalation policy would be a library nothing calls."""
    import tiered_loop
    state = tiered_loop.TieredState(context.agentic / "tiered.json")
    if args.response:
        reply = load(Path(args.response))
        index = args.index if args.index is not None else (
            state.open_escalations()[0]["index"] if state.open_escalations() else None)
        if index is None:
            say("no open escalation to answer", RED)
            return 1
        try:
            state.record_response(index, reply)
        except ValueError as error:
            state.save()
            say(f"REFUSED: {error}", RED)
            return 1
        state.save()
        say(f"recorded: {reply['verdict']}", GREEN if reply["verdict"] == "approve" else YELLOW)
        return 0
    outcome = state.pre_done(list(args.dimensions or []))
    state.save()
    if outcome["ready"]:
        say("done is unblocked", GREEN)
        if outcome.get("dimensions_reviewed_not_verified"):
            say("  these dimensions are REVIEWED, NOT VERIFIED — the manifest keeps them in "
                "the unverified column:", DIM)
            for dim in outcome["dimensions_reviewed_not_verified"]:
                say(f"    {dim}", DIM)
        return 0
    record = state.data["escalations"][outcome["escalation_index"]]
    brief = tiered_loop.review_brief(record, {"workspace": str(context.workspace)})
    target = context.agentic / "review-brief.md"
    target.write_text(brief, encoding="utf-8")
    say(f"BLOCKED: {outcome['reason']}", YELLOW)
    say(f"brief written: {target}", DIM)
    say(f"Run it with a strong subagent, save the JSON reply, then:  "
        f"awbp review --response <file> --index {outcome['escalation_index']}", DIM)
    return 1


def cmd_council_admit(context: Context, args: argparse.Namespace) -> int:
    """`awbp council-admit <memo.json>`: validate a reconciled memo and admit
    its invariants into the bootstrap suite (prose is rejected)."""
    import oracle_bootstrap
    import support_council
    payload = load(Path(args.memo))
    # accept either a full run_council package or a bare memo, but a package
    # that DISSENTED never admits: dissent means a human decides, and letting
    # council-admit swallow it would make the human gate decorative
    if "status" in payload and "memo" in payload:
        if payload["status"] != "agreed":
            say(f"REFUSED: council status is {payload['status']!r} — "
                "a dissent or invalid memo goes to a person, not into the suite", RED)
            return 1
        memo = payload["memo"]
    else:
        memo = payload
        say("note: bare memo (no countersign package) — admitting invariants without "
            "recorded agreement", YELLOW)
    validation = support_council.validate_memo(memo)
    if not validation["valid"]:
        say(f"MEMO REJECTED: {validation['reason']}", RED)
        return 1
    suite = oracle_bootstrap.BootstrapSuite(context.agentic / "bootstrap-suite.json")
    results = suite.admit_proposals(memo["invariants"], context.workspace, "council",
                                    note="support-council memo")
    suite.save()
    admitted = [r for r in results if r.get("admitted")]
    say(f"invariants admitted: {len(admitted)} / {len(results)}",
        GREEN if admitted else YELLOW)
    for row in results:
        if not row.get("admitted"):
            say(f"  rejected {row['id']}: {row['reason']}", DIM)
    return 0 if admitted or not memo["invariants"] else 1


def cmd_calibrate(context: Context, args: argparse.Namespace) -> int:
    """`awbp calibrate --baseline <dir> --accepted <dir> [--hollow <dir>]`:
    the full null/golden/adversarial triad, run once an accepted state exists —
    names which predicates are decoration."""
    import oracle_bootstrap
    suite = oracle_bootstrap.BootstrapSuite(context.agentic / "bootstrap-suite.json")
    report = suite.calibrate(Path(args.baseline), Path(args.accepted),
                             Path(args.hollow) if args.hollow else None)
    suite.save()
    dump(context.agentic / "calibration-report.json", report)
    say(f"sound: {len(report['sound'])}   decoration: {len(report['decoration'])}   "
        f"fakeable: {len(report['fakeable'])}",
        GREEN if not report["decoration"] and not report["fakeable"] else YELLOW)
    for row in report["rows"]:
        if row["verdict"] != "sound":
            say(f"  {row['id']}  [{row['source']}]  {row['verdict']}", DIM)
    return 0 if not report["decoration"] and not report["fakeable"] else 1


def cmd_deny_rules(context: Context, args: argparse.Namespace) -> int:
    """`awbp deny-rules [--paths a b c]`: emit deterministic permission deny
    rules for protected paths. A deny rule resolves BEFORE the probabilistic
    classifier; an allow rule does not guarantee the converse, so protection
    belongs in deny — the same mechanical-beats-judgement rule this whole
    environment runs on."""
    paths = list(args.paths or [])
    if not paths and context.project.exists():
        paths = load(context.project).get("protected_paths", [])
    if not paths:
        paths = [".agentic/**", ".git/**"]
        say("no protected paths declared; emitting the environment's own minimum", YELLOW)
    rules = {"permissions": {"deny": sorted({f"Write({p})" for p in paths}
                                            | {f"Edit({p})" for p in paths})}}
    target = context.agentic / "suggested-permissions.json"
    dump(target, rules)
    say(f"written: {target}", GREEN)
    say("Merge into .claude/settings.json. Deny is evaluated first and is deterministic;", DIM)
    say("an allow rule for the same path would still route through the classifier.", DIM)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="awbp", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workspace", type=Path, default=Path.cwd(),
                        help="the repository to work in (default: current directory)")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="detect the stack; verify the tests run today")
    init.add_argument("--no-verify", action="store_true")
    init.set_defaults(handler=cmd_init)

    task = sub.add_parser("task", help="route, snapshot the baseline, freeze the check suite")
    task.add_argument("text", nargs="*")
    task.add_argument("--task-file")
    task.add_argument("--state-lives-in", default="",
                      help='where user-visible state lives in production, e.g. '
                           '"postgres, shared across the internal team" or "browser-only (demo)"')
    task.set_defaults(handler=cmd_task)

    author = sub.add_parser("author", help="write the check-authoring brief (no provider call)")
    author.set_defaults(handler=cmd_author)

    admit = sub.add_parser("admit", help="admit an author's checks against the pre-change code")
    admit.add_argument("response", help="file holding the subagent's raw reply")
    admit.set_defaults(handler=cmd_admit)

    check = sub.add_parser("check", help="run the frozen suite once")
    check.set_defaults(handler=cmd_check)

    probe = sub.add_parser("probe", help="is the green earned? revert each hunk and see")
    probe.set_defaults(handler=cmd_probe)

    adversary = sub.add_parser("adversary", help="brief, then evaluate, an attack on the frozen checks")
    adversary.add_argument("response", nargs="?")
    adversary.set_defaults(handler=cmd_adversary)

    status = sub.add_parser("status", help="what this repo currently has")
    status.set_defaults(handler=cmd_status)

    bootstrap = sub.add_parser("bootstrap",
                               help="start the self-hardening suite for NEW work (relations at birth)")
    bootstrap.add_argument("--capture", nargs=argparse.REMAINDER, required=True,
                           help="everything after --capture is the command; {python} for the interpreter")
    bootstrap.set_defaults(handler=cmd_bootstrap)

    accept = sub.add_parser("accept", help="freeze the current tree as the accepted floor")
    accept.add_argument("--by", required=True, help="who accepted (person or reviewer profile)")
    accept.set_defaults(handler=cmd_accept)

    support = sub.add_parser("support",
                             help="budgeted council escalation (structured brief required)")
    support.add_argument("--decision", required=True)
    support.add_argument("--options", required=True)
    support.add_argument("--risks", required=True)
    support.add_argument("--missing", required=True,
                         help="what you might be missing — thinking this through IS the filter")
    support.set_defaults(handler=cmd_support)

    council_admit = sub.add_parser("council-admit",
                                   help="validate a reconciled memo; admit its invariants")
    council_admit.add_argument("memo", help="path to the reconciled memo JSON")
    council_admit.set_defaults(handler=cmd_council_admit)

    review = sub.add_parser("review",
                            help="T2 pre-done gate on named-unverified dimensions")
    review.add_argument("dimensions", nargs="*")
    review.add_argument("--response", help="file holding the reviewer's JSON reply")
    review.add_argument("--index", type=int)
    review.set_defaults(handler=cmd_review)

    calibrate = sub.add_parser("calibrate",
                               help="null/golden/adversarial triad over the bootstrap suite")
    calibrate.add_argument("--baseline", required=True, help="pre-work tree")
    calibrate.add_argument("--accepted", required=True, help="accepted (known-good) tree")
    calibrate.add_argument("--hollow", help="optional hollow/attack tree from capture_adversary")
    calibrate.set_defaults(handler=cmd_calibrate)

    deny_rules = sub.add_parser("deny-rules",
                                help="emit deterministic deny rules for protected paths")
    deny_rules.add_argument("--paths", nargs="*")
    deny_rules.set_defaults(handler=cmd_deny_rules)
    return parser


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    args = build_parser().parse_args()
    raise SystemExit(args.handler(Context(Path(args.workspace)), args))


if __name__ == "__main__":
    main()
