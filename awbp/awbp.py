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


def _short_command(command: list[str] | None, keep: int = 4) -> str:
    """A command line fit to read. Some runners take every test path explicitly."""
    command = list(command or [])
    if not command:
        return "(none detected)"
    if len(command) <= keep:
        return " ".join(command)
    return " ".join(command[:keep]) + f" ... (+{len(command) - keep} more paths)"


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
        if path.exists():
            return
        # The pre-change tree can be absent for two completely different reasons,
        # and one of them used to be reported as the other. Telling somebody to
        # "run awbp task" when they have just run it, and the snapshot was skipped
        # by a size cap they were never shown, sends them round a loop that cannot
        # terminate.
        if path == self.baseline:
            record_path = self.agentic / "baseline-record.json"
            record = load(record_path) if record_path.exists() else {}
            if record.get("snapshot") == "skipped-size-cap":
                say("No pre-change tree: the snapshot was SKIPPED at task time.", RED)
                say(f'  {record.get("total_bytes", 0) / 1048576:.1f} MB of tracked source '
                    f'exceeded the {record.get("max_bytes", 0) / 1048576:.0f} MB cap.', RED)
                say(f'  {record.get("lost", "")}', YELLOW)
                say(f'  {record.get("remedy", "")}', DIM)
                raise SystemExit(2)
        say(f"Missing: {path.name}. {hint}", RED)
        raise SystemExit(2)


def cmd_init(context: Context, args: argparse.Namespace) -> int:
    say(f"Detecting the stack in {context.workspace} ...", CYAN)
    arguments = ["--workspace", str(context.workspace)]
    if args.no_verify:
        arguments.append("--no-verify")
    code = run_step("project_detect.py", arguments)
    if code != 0:
        project = load(context.agentic / "project.json").get("test", {})
        run = project.get("baseline_run") or {}
        if project.get("command") and run.get("green") is False:
            # Distinguished from "no test command": the repository HAS a suite and
            # it is red. Saying "Ready" here, as this used to, offers an oracle
            # that cannot certify anything.
            say("\nNOT READY - the repository's own tests are RED before any agent work.", YELLOW)
            say("They cannot serve as an acceptance check until they pass. This is a fact", YELLOW)
            say("about the repo, not a failure of awbp.", YELLOW)
            say("\nEither fix the suite first, or proceed knowing the loop has only the symbol", YELLOW)
            say("sweep and the completion gate, with NO acceptance check:", YELLOW)
            say('    awbp task "<what you want done>"', DIM)
        else:
            say("\nNo test command could be identified.", YELLOW)
            say("The loop still gives you the symbol sweep and the completion gate, but acceptance", YELLOW)
            say("checks need a test command. Fix .agentic/project.json and re-run.", YELLOW)
        return code
    if args.no_verify:
        # Never a plain "Ready" here. Nothing has shown that this repo's suite
        # passes, so the acceptance check rests on an untested assumption and the
        # line that says so is the whole difference from a green nobody earned.
        say("\nReady, but the baseline was NOT verified (--no-verify).", YELLOW)
        say("Nothing has yet shown this repo's own tests pass today.", YELLOW)
        say('Next:  awbp task "<what you want done>"', DIM)
        return 0
    say('\nReady. The repo\'s own tests pass today, so they can serve as an acceptance check.',
        GREEN)
    say('Next:  awbp task "<what you want done>"', GREEN)
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
    # FACTS ACT BEFORE THE WORK STARTS. This is the consumer half of the store:
    # knowledge a previous session paid for changes THIS session's behaviour
    # mechanically, with no model comprehension in the loop. The concrete case
    # that earned the wiring: a snapshot silently skipped by a size cap, followed
    # by a probe telling the user to run the command they had just run.
    import facts_store as _facts
    _store = _facts.store_for(context.workspace)
    cap_fact = _store.get("baseline-exceeds-default-cap")
    if cap_fact and not getattr(args, "max_baseline_bytes", 0):
        recommended = int(cap_fact.data.get("recommended_bytes") or 0)
        if recommended:
            args.max_baseline_bytes = recommended
            say(f"Applying a recorded fact: baseline cap raised to "
                f"{recommended / 1048576:.0f} MB (learned "
                f"{cap_fact.first_recorded[:10]}, source: {cap_fact.source})", DIM)
    for fact in _store.open_facts("repo-fact"):
        if fact.key not in ("baseline-exceeds-default-cap",):
            say(f"Known about this repo: {fact.statement}", DIM)
    open_gaps = _store.open_facts("gap")
    if open_gaps:
        say(f"Open gaps recorded for this repo: {len(open_gaps)} "
            f"(awbp facts --report)", DIM)

    say("Routing and preparing ...", CYAN)
    prepare_args = ["--task-file", str(task_file), "--workspace", str(context.workspace)]
    if getattr(args, "max_baseline_bytes", 0):
        prepare_args += ["--max-baseline-bytes", str(args.max_baseline_bytes)]
    code = run_step("prepare_context.py", prepare_args)
    if code != 0:
        return code

    # A SKIPPED SNAPSHOT IS A LOST CAPABILITY, SO IT IS SAID OUT LOUD. It used to
    # be recorded in JSON and nowhere else: on a large repository `task` printed
    # "Prepared", and `probe` then answered "No baseline snapshot. Run: awbp task"
    # to somebody who had just run exactly that.
    record = load(context.agentic / "baseline-record.json") if (
        context.agentic / "baseline-record.json").exists() else {}
    if record.get("snapshot") == "skipped-size-cap":
        say("")
        say("NO BASELINE SNAPSHOT - this workspace is larger than the cap.", YELLOW)
        say(f'  {record.get("total_bytes", 0) / 1048576:.1f} MB of tracked source, '
            f'cap {record.get("max_bytes", 0) / 1048576:.0f} MB', YELLOW)
        say(f'  LOST: {record.get("lost", "")}', YELLOW)
        say(f'  {record.get("remedy", "")}', DIM)

    # WHERE DOES THE STATE LIVE? Asked at the START, because the answer stops
    # being cheap later. A task once scoped "local-first is fine and expected"
    # produced a polished TEAM board that stored the team's ideas in one person's
    # browser. The scope line was correct; nothing connected it to shippability,
    # and nobody noticed until the owner asked whether it worked in production.
    # "browser-only (demo)" is a fine answer — it just has to be CHOSEN.
    if getattr(args, "state_lives_in", ""):
        state_file = context.agentic / "state.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(
            json.dumps({"state_lives_in": args.state_lives_in}, indent=1) + "\n", encoding="utf-8")
        say(f"State recorded: {args.state_lives_in}", GREEN)
    else:
        say("\nIf this task creates or changes state a USER can see, answer this now:", YELLOW)
        say("  where does that state live in production, and who else can see it?")
        say('  awbp task ... --state-lives-in "postgres, shared across the internal team"')
        say('  --state-lives-in "browser-only (demo)" is a valid answer; defaulting into it is not.')

    # WHERE WILL THE ORACLE COME FROM? Asked FIRST, ahead of mode and strategy,
    # because it decides how much any later green is worth. The mode ladder was
    # measured at zero for correctness; the source of the oracle is what the two
    # positive campaigns actually differed on.
    import oracle_plan

    plan = oracle_plan.plan(context.workspace, task_file.read_text(encoding="utf-8-sig"))
    (context.agentic / "oracle-plan.json").write_text(
        json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    say("", DIM)
    say(oracle_plan.render(plan), CYAN if plan["verdict"] != "WEAK" else YELLOW)
    if plan["verdict"] == "WEAK":
        say("\n  A green from a spec-only instrument means the work agrees with its own "
            "description. Say so in the report.", YELLOW)

    # WHO DOES THE WORK AND WHO CHECKS IT. Declared at the start, because the
    # measured answer is "it depends on the task": on one client deliverable a
    # cheap executor with a strong reviewer produced the best-formatted output at
    # 52% of the cost and dropped three of four checkable figures. A default would
    # be a guess dressed as a policy, so the agent declares and the reason is kept.
    import execution_strategy

    # THE ENVIRONMENT PROPOSES; AN EXPLICIT CHOICE ALWAYS WINS. Leaving this to a
    # flag meant the answer in practice was "whatever the human remembered to
    # type", which is not a decision the environment made and cannot be correlated
    # with anything. The proposal is derived from the task text and from what the
    # oracle plan just found, and it carries its own confidence, which is low.
    proposal = execution_strategy.propose(
        task_file.read_text(encoding="utf-8-sig"),
        oracle_verdict=plan["verdict"],
        risk=getattr(args, "risk", "medium"),
        available_sources=[s["source"] for s in plan["sources"] if s["available"]])

    chosen = getattr(args, "strategy", "") or proposal["proposed"]
    reason = args.reason or ("" if getattr(args, "strategy", "") else proposal["reason"])
    origin = "declared by you" if getattr(args, "strategy", "") else "proposed by the environment"

    try:
        record = execution_strategy.declare(chosen, reason, args.risk,
                                            executor_profile=getattr(args, "executor", "") or None)
    except ValueError as error:
        say(f"\n{error}", RED)
        return 2
    record["origin"] = origin
    record["proposal"] = proposal
    (context.agentic / "execution-strategy.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8")

    roles = record["models"]["roles"]
    say(f"\nStrategy: {record['strategy']}  ({origin})   "
        f"executor={(roles.get('executor') or {}).get('selector')}   "
        f"reviewer={(roles.get('reviewer') or {}).get('selector') or '-'}", GREEN)
    for signal in proposal["signals"]:
        say(f"    · {signal}", DIM)
    if origin.startswith("proposed"):
        say(f"    confidence: {proposal['confidence']} — {proposal['basis']}", DIM)
        say(f'    override:  awbp task ... --strategy solo|reviewed|council|full '
            f'--reason "<why THIS task>"', DIM)

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
    report = load(context.agentic / "necessity-report.json")
    if report.get("nothing_to_probe"):
        # Distinguished from NOT EARNED on purpose: nothing is wrong with the
        # change, there is no change. Collapsing the two would teach the reader
        # that an empty diff is a failing diff, which is a different lie.
        say("NOTHING TO PROBE - the workspace matches the baseline.", YELLOW)
        say("This is not a pass. 'Is the green earned' has no answer when nothing "
            "was changed.", YELLOW)
    elif code == 0:
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
    # Truncated, for the same reason `init` truncates it: on a repo whose runner
    # takes explicit paths the command IS every test file, and `status` exists to
    # be read at a glance. Fixed in init first and missed here, which is why the
    # rule is now in one helper.
    say(f"test command  {_short_command(project_detect.test_command(project))}")
    say(f"evidence      {project_detect.test_evidence(project)}")
    if context.suite.exists():
        suite = load(context.suite)
        say(f"frozen suite  {len(suite.get('checks', []))} checks")
        for check in suite.get("checks", []):
            say(f"  {check.get('id')}  [{check.get('kind')}]", DIM)
    else:
        say('frozen suite  none - run:  awbp task "<text>"')
    return 0


def cmd_demo(context: Context, args: argparse.Namespace) -> int:
    """The shop window. Runs against the shipped fixture, never the user's repo."""
    import demo as demo_module
    return demo_module.main([])


def cmd_support(context: Context, args: argparse.Namespace) -> int:
    """Emit the briefs for the DECLARED support roles, so the driving agent can
    dispatch them as subagents. Until this command existed nothing turned the
    strategy record into anything a session could actually run, which made
    `reviewed` a label rather than a mechanism. No provider call happens here."""
    import support_briefs

    strategy_file = context.agentic / "execution-strategy.json"
    context.require(strategy_file, 'Run:  awbp task "<text>"  first (it declares the strategy)')
    record = load(strategy_file)
    task_text = context.task_file.read_text(encoding="utf-8-sig") if context.task_file.exists() else ""
    emitted = support_briefs.emit(record, task_text, context.agentic)
    if not emitted:
        say("Strategy is 'solo': no support roles are declared, so there is nothing to brief.", YELLOW)
        return 0
    say(f"Support briefs for strategy {record['strategy']!r}:", GREEN)
    for role, model, name in emitted:
        say(f"  {role:<11} -> spawn a {model} subagent with .agentic/{name}", CYAN)
    say("Save each response to a file; reviewer findings are evidence to resolve,", DIM)
    say("not decoration.", DIM)
    return 0


def cmd_facts(context: Context, args: argparse.Namespace) -> int:
    import facts_store
    from datetime import datetime, timezone
    store = facts_store.store_for(context.workspace)
    if args.close:
        ok = store.close(args.close, datetime.now(timezone.utc).isoformat(timespec="seconds"))
        say(f"{'closed' if ok else 'NOT FOUND'}: {args.close}", GREEN if ok else RED)
        return 0 if ok else 1
    say(store.render())
    return 0


def cmd_mcp(context: Context, args: argparse.Namespace) -> int:
    """Read-only tools over stdio. The workspace comes from each call, not from here."""
    import mcp_server
    return mcp_server.main(["--tools"] if args.tools else [])


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
    task.add_argument("--strategy", choices=["solo", "reviewed", "council", "full"], default="",
                      help="who does the work and who checks it (execution_strategy.py --list)")
    task.add_argument("--reason", default="", help="why THIS task warrants that strategy")
    task.add_argument("--executor", default="",
                      choices=["fast-low-risk", "balanced-daily", "architecture-high-risk"],
                      help="override the base tier: the support stack and the executor are "
                           "orthogonal knobs ('opus solo' = --strategy solo --executor "
                           "architecture-high-risk)")
    task.add_argument("--risk", default="medium", choices=["low", "medium", "high", "critical"])
    task.add_argument("--max-baseline-bytes", type=int, default=0,
                      help="raise the pre-change snapshot size cap for a large repository")
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

    demo = sub.add_parser("demo", help="see the whole idea in ten seconds (no provider call)")
    demo.set_defaults(handler=cmd_demo)

    support = sub.add_parser("support", help="emit briefs for the declared reviewer/council roles")
    support.set_defaults(handler=cmd_support)

    facts = sub.add_parser("facts", help="what this repo's store knows (paid-for facts, prefs, gaps)")
    facts.add_argument("--close", metavar="KEY", help="close a gap that has been built")
    facts.set_defaults(handler=cmd_facts)

    mcp = sub.add_parser("mcp", help="serve the read-only tools over MCP stdio")
    mcp.add_argument("--tools", action="store_true", help="list the tools and exit")
    mcp.set_defaults(handler=cmd_mcp)
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
