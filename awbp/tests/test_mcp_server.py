#!/usr/bin/env python3
"""The MCP server is a promise made to other agents, so it is tested like one.

Two things are being checked, and only one of them is the protocol.

The protocol half is mechanical: initialize, tools/list, tools/call, a bad tool
name, a bad path, notifications that must produce NO response at all. A server
that answers a notification corrupts the stream for every message after it.

The half that actually matters is that the tools stay READ-ONLY. Something
reachable over a socket must not be able to write to a stranger's repository as a
side effect of answering a question, so the read-only claim is asserted by
fingerprinting a repository before and after every tool runs against it.

    python tests/test_mcp_server.py
"""
from __future__ import annotations

import hashlib
import io
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mcp_server              # noqa: E402

PASS, FAIL = [], []


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASS if condition else FAIL).append(f"{name}{' — ' + detail if detail else ''}")


def call(method: str, params: dict | None = None, request_id: int | None = 1):
    message = {"jsonrpc": "2.0", "method": method}
    if request_id is not None:
        message["id"] = request_id
    if params is not None:
        message["params"] = params
    return mcp_server.handle(message)


def text_of(response: dict) -> str:
    return response["result"]["content"][0]["text"]


def fingerprint(root: Path) -> dict[str, str]:
    out = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            out[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def sample_repo(root: Path) -> Path:
    repo = root / "sample"
    (repo / "src").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "src" / "theme.css").write_text(":root { --ink: #101820; --gap: 4px; }",
                                            encoding="utf-8")
    (repo / "tests" / "test_a.py").write_text("assert True", encoding="utf-8")
    return repo


# ── protocol ──────────────────────────────────────────────────────────────────
def test_initialize() -> None:
    result = call("initialize", {"protocolVersion": mcp_server.PROTOCOL_VERSION})["result"]
    check("initialize returns a protocol version",
          result["protocolVersion"] == mcp_server.PROTOCOL_VERSION)
    check("initialize declares the tools capability", "tools" in result["capabilities"])
    check("initialize names the server", result["serverInfo"]["name"] == "awbp")


def test_notifications_get_no_response() -> None:
    # A response to a notification is an extra line the client never asked for,
    # and every message after it reads one slot out of step.
    check("initialized notification is silent",
          call("notifications/initialized", None, request_id=None) is None)
    check("an unknown notification is silent",
          call("some/other/notification", None, request_id=None) is None)


def test_tools_list_is_complete_and_well_formed() -> None:
    tools = call("tools/list")["result"]["tools"]
    names = {tool["name"] for tool in tools}
    check("every advertised tool is listed",
          names == set(mcp_server.HANDLERS), str(names))
    for tool in tools:
        check(f"{tool['name']}: has a description over 40 chars",
              len(tool.get("description", "")) > 40)
        schema = tool.get("inputSchema") or {}
        check(f"{tool['name']}: input schema is an object", schema.get("type") == "object")
        for required in schema.get("required", []):
            check(f"{tool['name']}: required field {required!r} is declared",
                  required in schema.get("properties", {}))


def test_unknown_tool_is_a_protocol_error() -> None:
    response = call("tools/call", {"name": "nope", "arguments": {}})
    check("unknown tool returns an error object", "error" in response)
    check("unknown tool names itself", "nope" in response["error"]["message"])


def test_unknown_method_is_reported() -> None:
    response = call("frobnicate")
    check("unknown method returns an error", "error" in response)


# ── tools ─────────────────────────────────────────────────────────────────────
def test_oracle_plan(repo: Path) -> None:
    body = text_of(call("tools/call", {"name": "oracle_plan",
                                       "arguments": {"repo": str(repo)}}))
    check("oracle_plan reports a verdict", "ORACLE PLAN:" in body)
    check("oracle_plan finds the repo's own suite", "repo-tests" in body)
    check("oracle_plan returns parseable json too",
          json.loads(body[body.index("{"):])["verdict"] in {"STRONG", "WORKABLE", "WEAK"})


def test_bad_path_is_a_tool_error_not_a_crash() -> None:
    response = call("tools/call", {"name": "oracle_plan",
                                   "arguments": {"repo": "/definitely/not/here"}})
    check("a bad path is reported as a tool error", response["result"].get("isError") is True)
    check("a bad path says what was wrong",
          "not a directory" in text_of(response), text_of(response)[:60])
    response = call("tools/call", {"name": "oracle_plan", "arguments": {}})
    check("a missing repo argument is reported", response["result"].get("isError") is True)


def test_host_rules(repo: Path) -> None:
    listing = text_of(call("tools/call", {"name": "host_rules",
                                          "arguments": {"repo": str(repo)}}))
    check("host_rules discovers or explains", "HOST FILES" in listing or "No host files" in listing)

    body = text_of(call("tools/call", {"name": "host_rules",
                                       "arguments": {"repo": str(repo),
                                                     "file": "src/theme.css"}}))
    payload = json.loads(body)
    check("host_rules extracts css variables",
          payload["values"]["variables"]["--ink"] == "#101820", str(payload)[:80])
    check("host_rules stamps host provenance", payload["provenance"] == "host")


def test_check_calibration() -> None:
    working = text_of(call("tools/call", {"name": "check_calibration",
                                          "arguments": {"good_score": 0.9,
                                                        "hollow_score": 0.1}}))
    check("a separating instrument may grade", '"may_grade": true' in working.lower())

    blind = text_of(call("tools/call", {"name": "check_calibration",
                                        "arguments": {"good_score": 0.9,
                                                      "hollow_score": 0.9}}))
    check("an instrument that passes a fake may NOT grade",
          '"may_grade": false' in blind.lower(), blind[:90])


def test_coverage_manifest() -> None:
    # Deliberately the WRONG field names: `title` for `statement`, `dimension` for
    # `covers`. An agent calling over a socket cannot read the source, and the
    # first version of this tool answered such a call with a beautifully formatted
    # report saying nothing was covered. A confident wrong answer, not an error.
    body = text_of(call("tools/call", {"name": "coverage_manifest", "arguments": {
        "dimensions": [{"id": "d1", "title": "rows survive a retry"},
                       {"id": "d2", "title": "order is preserved"}],
        "checks": [{"id": "c1", "dimension": "d1", "provenance": "authored", "passed": True}],
    }}))
    check("the report opens with what is NOT covered", "NOT MECHANICALLY COVERED" in body, body[:80])
    check("the uncovered dimension is named, not just its id",
          "order is preserved" in body, body[:120])
    check("a covered dimension is not listed as uncovered",
          "rows survive a retry" not in body.split("ORACLE INDEPENDENCE")[0], body[:160])

    # And the correct field names must of course still work.
    proper = text_of(call("tools/call", {"name": "coverage_manifest", "arguments": {
        "dimensions": [{"id": "d1", "statement": "rows survive a retry"}],
        "checks": [{"id": "c1", "covers": ["d1"], "provenance": "diff-derived"}],
    }}))
    check("a diff-derived check reaches full independence",
          "ORACLE INDEPENDENCE: 100%" in proper, proper[:140])


def test_demo() -> None:
    body = text_of(call("tools/call", {"name": "demo", "arguments": {}}))
    check("demo reports arm 1 as done", "VERDICT: done." in body)
    check("demo reports the uncovered behaviours", "NOT MECHANICALLY COVERED" in body)


def test_every_tool_is_read_only(repo: Path) -> None:
    """The claim in the module docstring, asserted rather than promised."""
    before = fingerprint(repo)
    for name in mcp_server.HANDLERS:
        arguments = {"repo": str(repo)} if name in ("oracle_plan", "host_rules") else {}
        if name == "check_calibration":
            arguments = {"good_score": 0.8, "hollow_score": 0.2}
        if name == "coverage_manifest":
            arguments = {"dimensions": [{"id": "d1", "title": "t"}], "checks": []}
        call("tools/call", {"name": name, "arguments": arguments})
    after = fingerprint(repo)
    check("no tool modified the repository", before == after,
          str(set(before) ^ set(after)) or "contents changed")


def test_serve_round_trip(repo: Path) -> None:
    """The real loop: newline-delimited json in, newline-delimited json out."""
    lines = [
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
        json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
        json.dumps({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                    "params": {"name": "oracle_plan", "arguments": {"repo": str(repo)}}}),
        "",
        "{ not json",
    ]
    out = io.StringIO()
    mcp_server.serve(io.StringIO("\n".join(lines) + "\n"), out)
    responses = [json.loads(line) for line in out.getvalue().splitlines() if line.strip()]
    check("blank lines produce nothing and the notification is silent",
          len(responses) == 4, f"{len(responses)} responses")
    check("responses come back in order",
          [r.get("id") for r in responses[:3]] == [1, 2, 3],
          str([r.get("id") for r in responses]))
    check("malformed json is reported, not fatal", responses[-1]["error"]["code"] == -32700)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    test_initialize()
    test_notifications_get_no_response()
    test_tools_list_is_complete_and_well_formed()
    test_unknown_tool_is_a_protocol_error()
    test_unknown_method_is_reported()
    test_bad_path_is_a_tool_error_not_a_crash()
    test_check_calibration()
    test_coverage_manifest()
    test_demo()

    with tempfile.TemporaryDirectory() as raw:
        repo = sample_repo(Path(raw))
        test_oracle_plan(repo)
        test_host_rules(repo)
        test_every_tool_is_read_only(repo)
        test_serve_round_trip(repo)

    for line in PASS:
        print(f"  ok    {line}")
    for line in FAIL:
        print(f"  FAIL  {line}")
    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
