#!/usr/bin/env python3
"""Earned Green over MCP: the instrument, without cloning the instrument.

    python -m awbp mcp          # speaks MCP over stdio

Registered in an agent's MCP config, this gives any assistant the four questions
this repository exists to ask, applied to whatever repository the user is in:

    oracle_plan          where will this task's oracle come from, and what is a
                         green from it actually worth?
    host_rules           extract the repo's own conventions mechanically, so a
                         rule cannot drift from the file it came from
    check_calibration    refuse a verdict from an instrument that has not shown
                         it can tell known-good from known-hollow
    coverage_manifest    report what is NOT covered first, with the share of
                         checks that came from somewhere other than the author
    demo                 the shop-window run, for explaining any of the above

WHY THIS FILE HAS NO DEPENDENCIES. It implements the protocol directly over
stdio: JSON-RPC 2.0, one message per line. An SDK would be shorter, but a tool
whose whole argument is "your green is worth what its oracle is worth" cannot
reasonably ask you to install a dependency tree before it will tell you that.
Standard library only, and it starts in milliseconds.

WHAT IT WILL NOT DO. Nothing here writes to your repository, runs your tests, or
makes a provider call. Every tool below reads. The commands that write live in
`awbp` proper and stay there, because an agent reaching through a socket should
not be able to snapshot your workspace as a side effect of asking a question.
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import calibration_gate            # noqa: E402
import coverage_manifest           # noqa: E402
import host_rules                  # noqa: E402
import oracle_plan                 # noqa: E402

PROTOCOL_VERSION = "2024-11-05"
SERVER = {"name": "awbp", "version": "0.6.6"}

_PATH = {"type": "string", "description": "absolute path to the repository"}

TOOLS = [
    {
        "name": "oracle_plan",
        "description": (
            "Ask BEFORE writing code: where will this task's oracle come from? Reports every "
            "oracle source this repository can actually supply, ranked by a measured ladder "
            "(diff-derived/data/repo-tests=4, host=3, spec=2, agent-authored=1), and says WEAK "
            "to your face when the only thing available is the task description. Read-only, "
            "about a second on a large repo."),
        "inputSchema": {
            "type": "object",
            "properties": {"repo": _PATH,
                           "task": {"type": "string",
                                    "description": "the task text, if you have it"}},
            "required": ["repo"],
        },
    },
    {
        "name": "host_rules",
        "description": (
            "Extract a repository's own conventions mechanically from the file the product "
            "already renders from: design tokens, theme files, brand modules, CSS custom "
            "properties, or written MUST/NEVER directives. Transcribing such rules by hand "
            "drops them from rank 3 to rank 2 and stops them tracking the source. Call with "
            "no `file` to list the host files this repo has."),
        "inputSchema": {
            "type": "object",
            "properties": {"repo": _PATH,
                           "file": {"type": "string",
                                    "description": "one host file to extract from; omit to discover"}},
            "required": ["repo"],
        },
    },
    {
        "name": "check_calibration",
        "description": (
            "Before trusting ANY grade: re-grade a known-good and a known-hollow fixture "
            "through the same path and refuse a verdict if the instrument cannot separate "
            "them. A result from an uncalibrated instrument is not a weak result, it is not a "
            "result. Pass the two scores this instrument gave those two fixtures."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "good_score": {"type": "number",
                               "description": "score the instrument gave the KNOWN-GOOD fixture"},
                "hollow_score": {"type": "number",
                                 "description": "score it gave the KNOWN-HOLLOW fixture"},
            },
            "required": ["good_score", "hollow_score"],
        },
    },
    {
        "name": "coverage_manifest",
        "description": (
            "Build the report that opens with the GAP: which requested behaviours no check "
            "mechanically covers, then the share of checks whose provenance is independent of "
            "whoever did the work, and only then the green. Pass the behaviours you were asked "
            "for and the checks you actually have."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "dimensions": {
                    "type": "array",
                    "description": ("the behaviours asked for; each {id, statement}. `statement` is "
                                    "the behaviour in plain words and is what the report prints, "
                                    "so an id alone leaves the reader knowing that something is "
                                    "uncovered but not what"),
                    "items": {"type": "object"},
                },
                "checks": {
                    "type": "array",
                    "description": ("the checks you have; each {id, covers, provenance}. `covers` "
                                    "is the list of dimension ids this check actually pins - a "
                                    "check that covers nothing contributes nothing. `provenance` "
                                    "is one of diff-derived, data, repo-tests, host, relation, "
                                    "acceptance, finding, spec, authored, council, "
                                    "reviewed-unverified"),
                    "items": {"type": "object"},
                },
            },
            "required": ["dimensions", "checks"],
        },
    },
    {
        "name": "demo",
        "description": (
            "Run the shipped demonstration: one change, checked twice. The suite the change "
            "wrote for itself passes 7 of 7 and reports done; predicates derived from the "
            "module's own repair history fail 2. Useful for explaining, in one output, why an "
            "agent's own checks are not evidence. No provider call, no network, under a second."),
        "inputSchema": {"type": "object", "properties": {}},
    },
]


# ── tool implementations ──────────────────────────────────────────────────────
def _repo(arguments: dict) -> Path:
    raw = (arguments or {}).get("repo") or ""
    path = Path(raw).expanduser()
    if not raw:
        raise ValueError("`repo` is required: give the absolute path to the repository")
    if not path.is_dir():
        raise ValueError(f"not a directory: {path}")
    return path.resolve()


def tool_oracle_plan(arguments: dict) -> str:
    repo = _repo(arguments)
    result = oracle_plan.plan(repo, (arguments or {}).get("task", ""))
    return oracle_plan.render(result) + "\n\n" + json.dumps(
        {"verdict": result["verdict"],
         "strongest_available": result["strongest_available"],
         "independence_ceiling": result["independence_ceiling"]}, indent=2)


def tool_host_rules(arguments: dict) -> str:
    repo = _repo(arguments)
    target = (arguments or {}).get("file")
    if not target:
        hits = host_rules.discover(repo)
        if not hits:
            return ("No host files found. This repository's strongest oracle is not `host`; "
                    "run oracle_plan to see what it does have.")
        lines = [f"HOST FILES ({len(hits)}) - extract, do not transcribe", ""]
        for hit in hits:
            rules = host_rules.extract(hit)
            lines.append(f"  {'ok   ' if rules.usable else 'EMPTY'} {rules.count:>5} rules  "
                         f"{rules.extractor:<14} {hit.relative_to(repo)}")
        return "\n".join(lines)

    path = (repo / target) if not Path(target).is_absolute() else Path(target)
    rules = host_rules.extract(path)
    return json.dumps(rules.as_dict(), indent=2, default=str)


def tool_check_calibration(arguments: dict) -> str:
    verdict = calibration_gate.CalibrationGate().check(
        float(arguments["good_score"]), float(arguments["hollow_score"]))
    return verdict.report() + "\n\n" + json.dumps(verdict.to_dict(), indent=2, default=str)


def tool_coverage_manifest(arguments: dict) -> str:
    # ALIASES ARE NORMALISED, NOT REJECTED. A caller reaching this over a socket
    # cannot read the source to learn that the field is `covers` and not
    # `dimension`. Getting it wrong produced a perfectly formatted report saying
    # nothing was covered, which is a confident wrong answer rather than an error.
    dimensions = [{**row, "statement": row.get("statement") or row.get("title") or row.get("id", "")}
                  for row in arguments["dimensions"]]
    checks = []
    for row in arguments["checks"]:
        covers = row.get("covers")
        if covers is None:
            single = row.get("dimension") or row.get("dimension_id")
            covers = [single] if single else []
        checks.append({**row, "covers": [covers] if isinstance(covers, str) else list(covers)})

    manifest = coverage_manifest.build(dimensions, checks)
    report = coverage_manifest.render(manifest)
    if checks and not any(c["covers"] for c in checks):
        report += ("\n\nNOTE: not one check named a dimension it covers, so nothing could be "
                   "credited. Each check needs `covers: [<dimension id>, ...]`.")
    return report


def tool_demo(_arguments: dict) -> str:
    import io
    from contextlib import redirect_stdout
    import demo as demo_module
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        demo_module.main([])
    return buffer.getvalue()


HANDLERS = {
    "oracle_plan": tool_oracle_plan,
    "host_rules": tool_host_rules,
    "check_calibration": tool_check_calibration,
    "coverage_manifest": tool_coverage_manifest,
    "demo": tool_demo,
}


# ── protocol ──────────────────────────────────────────────────────────────────
def handle(message: dict) -> dict | None:
    """One request in, one response out. None means notification: say nothing."""
    method = message.get("method")
    request_id = message.get("id")

    if method == "initialize":
        return _ok(request_id, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": SERVER,
        })
    if method in ("notifications/initialized", "initialized"):
        return None
    if method == "ping":
        return _ok(request_id, {})
    if method == "tools/list":
        return _ok(request_id, {"tools": TOOLS})
    if method == "tools/call":
        params = message.get("params") or {}
        name = params.get("name")
        handler = HANDLERS.get(name)
        if handler is None:
            return _error(request_id, -32602, f"unknown tool: {name}")
        try:
            text = handler(params.get("arguments") or {})
        except Exception as exc:                       # noqa: BLE001
            # Reported as a TOOL result, not a protocol error. The distinction
            # matters to the caller: a bad path is something the agent can fix and
            # retry, and burying it in a JSON-RPC error makes it look like the
            # server broke.
            return _ok(request_id, {
                "content": [{"type": "text",
                             "text": f"{type(exc).__name__}: {exc}\n\n"
                                     f"{traceback.format_exc(limit=3)}"}],
                "isError": True,
            })
        return _ok(request_id, {"content": [{"type": "text", "text": text}]})

    if request_id is None:
        return None
    return _error(request_id, -32601, f"method not found: {method}")


def _ok(request_id, result) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id, code, message) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def serve(stdin=None, stdout=None) -> int:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            stdout.write(json.dumps(_error(None, -32700, f"parse error: {exc}")) + "\n")
            stdout.flush()
            continue
        response = handle(message)
        if response is not None:
            stdout.write(json.dumps(response) + "\n")
            stdout.flush()
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdin.reconfigure(encoding="utf-8")
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] in ("--tools", "-l"):
        for tool in TOOLS:
            print(f"  {tool['name']:<20} {tool['description'][:96]}")
        return 0
    if argv and argv[0] in ("--help", "-h"):
        print(__doc__)
        return 0
    return serve()


if __name__ == "__main__":
    raise SystemExit(main())
