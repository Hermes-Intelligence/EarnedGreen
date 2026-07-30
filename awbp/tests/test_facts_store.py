#!/usr/bin/env python3
"""Facts consumed by tools, not lessons read by models.

The rehabilitated notes_bank. What measured zero was prose routed through model
comprehension; every test here guards the property that dodges that failure:
a fact is written by a tool, read by a tool, and ACTS mechanically.

The load-bearing assertions:
  - the rediscovery counter (the owner's longitudinal metric) increments only on
    the WRITE path, never on reads — a reader consuming a fact is the mechanism
    working, not a session paying twice;
  - a fact with no consumer is accepted but reported as advisory, FIRST — because
    an unconsumed fact is prose with better formatting, and prose measured zero;
  - the end-to-end loop: the snapshot-cap fact recorded by harness_checks is
    APPLIED by awbp task in a later session without a human retyping anything.

    python tests/test_facts_store.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import facts_store          # noqa: E402

PASS, FAIL = [], []
T0, T1, T2 = "2026-07-22T10:00:00+00:00", "2026-07-22T11:00:00+00:00", "2026-07-23T09:00:00+00:00"


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASS if condition else FAIL).append(f"{name}{' — ' + detail if detail else ''}")


def test_new_then_rediscovered(tmp: Path) -> None:
    store = facts_store.FactsStore(tmp / "facts.jsonl")
    first = store.record("suite-mutates-tree", "repo-fact", "suite rewrites 4 files",
                         source="project_detect", now=T0,
                         enforced_by="awbp init warning")
    check("first write is new", first["verdict"] == "new")

    again = store.record("suite-mutates-tree", "repo-fact", "suite rewrites 4 files",
                         source="project_detect", now=T1)
    check("second ARRIVAL at the same knowledge counts as rediscovery",
          again["verdict"] == "rediscovered" and again["times_rediscovered"] == 1)
    check("the rediscovery names what it means",
          "paid again" in again["note"], again.get("note", "")[:50])


def test_reads_never_count_as_rediscovery(tmp: Path) -> None:
    """Consuming a fact is the mechanism WORKING. Only re-deriving it is a cost."""
    store = facts_store.FactsStore(tmp / "reads.jsonl")
    store.record("k", "repo-fact", "s", source="t", now=T0, enforced_by="x")
    store.get("k")
    store.touch("k", T1)
    store.open_facts()
    check("reads and touches do not move the metric",
          store.get("k").times_rediscovered == 0)
    check("touch refreshes last_seen", store.get("k").last_seen == T1)


def test_persistence_across_sessions(tmp: Path) -> None:
    """The whole point: session N+1 opens the file and knows what N paid for."""
    path = tmp / "persist.jsonl"
    facts_store.FactsStore(path).record(
        "baseline-exceeds-default-cap", "repo-fact", "78.7 MB tracked",
        source="harness_checks", now=T0,
        enforced_by="awbp task (auto-raises cap)",
        data={"recommended_bytes": 90_000_000})

    later = facts_store.FactsStore(path)          # a fresh session
    fact = later.get("baseline-exceeds-default-cap")
    check("a later session reads the fact", fact is not None)
    check("the machine payload survives", fact.data["recommended_bytes"] == 90_000_000)
    check("the consumer is named", "auto-raises" in fact.enforced_by)


def test_unconsumed_facts_are_advisory_and_loud(tmp: Path) -> None:
    store = facts_store.FactsStore(tmp / "advisory.jsonl")
    store.record("wired", "repo-fact", "has a consumer", source="t", now=T0,
                 enforced_by="something.py")
    store.record("orphan", "repo-fact", "nothing consumes this", source="t", now=T0)
    report = store.report()
    check("the unconsumed fact is reported", report["advisory_unconsumed"] == ["orphan"])
    rendered = store.render()
    check("advisory section renders FIRST",
          rendered.index("ADVISORY") < rendered.index("rediscoveries"), rendered[:120])
    check("the rule states why", "prose" in report["rule"])


def test_gap_lifecycle(tmp: Path) -> None:
    store = facts_store.FactsStore(tmp / "gaps.jsonl")
    store.record("gap:endpoint:/vextrum/municipalities", "gap",
                 "no endpoint serves municipality aggregates",
                 source="binding-checker", now=T0,
                 enforced_by="workspace-spec binding checker")
    check("open gap is listed",
          len(store.open_facts("gap")) == 1)
    check("closing works", store.close("gap:endpoint:/vextrum/municipalities", T2))
    check("closed gap leaves the open list", store.open_facts("gap") == [])
    check("closed gap is still in the store (history, not deletion)",
          store.get("gap:endpoint:/vextrum/municipalities").status == "closed")


def test_unknown_kind_is_refused(tmp: Path) -> None:
    store = facts_store.FactsStore(tmp / "kind.jsonl")
    try:
        store.record("k", "lesson", "prose lesson", source="t", now=T0)
        check("the prose kind is refused", False, "it was accepted")
    except ValueError as exc:
        check("the prose kind is refused", "lesson" in str(exc))


def test_corrupt_line_does_not_kill_the_store(tmp: Path) -> None:
    path = tmp / "corrupt.jsonl"
    facts_store.FactsStore(path).record("good", "repo-fact", "s", source="t", now=T0,
                                        enforced_by="x")
    with path.open("a", encoding="utf-8") as handle:
        handle.write("{ not json\n")
    survived = facts_store.FactsStore(path)
    check("a corrupt line is skipped, the store survives", survived.get("good") is not None)


def test_end_to_end_cap_fact_is_applied_by_task(tmp: Path) -> None:
    """The wiring, not just the store: harness writes, awbp task READS AND ACTS."""
    import importlib
    import json
    workspace = tmp / "repo"
    (workspace / "src").mkdir(parents=True)
    (workspace / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    # An already-initialised repo: cmd_task must reach the facts code, not bail
    # into init on a fixture that has no test suite.
    (workspace / ".agentic").mkdir()
    (workspace / ".agentic" / "project.json").write_text(json.dumps({
        "schema_version": 1, "detected_at_root": "repo",
        "test": {"command": ["python", "-c", "pass"], "runner": "none",
                 "evidence": "fixture"},
        "test_dir": "", "source_globs": ["src/**"], "vcs": "none",
    }), encoding="utf-8")

    facts_store.store_for(workspace).record(
        "baseline-exceeds-default-cap", "repo-fact", "big repo",
        source="harness_checks.snapshot_baseline", now=T0,
        enforced_by="awbp task (auto-raises the cap from this fact)",
        data={"recommended_bytes": 777_000_000})

    awbp = importlib.import_module("awbp")
    import argparse, io
    from contextlib import redirect_stdout
    args = argparse.Namespace(task_file="", text=["do", "a", "thing"], strategy="",
                              reason="", risk="medium", state_lives_in="none",
                              max_baseline_bytes=0)
    buffer = io.StringIO()
    try:
        with redirect_stdout(buffer):
            awbp.cmd_task(awbp.Context(workspace), args)
    except SystemExit:
        pass
    check("task auto-applies the recorded cap", args.max_baseline_bytes == 777_000_000,
          f"got {args.max_baseline_bytes}")
    check("and says where the knowledge came from",
          "Applying a recorded fact" in buffer.getvalue(), buffer.getvalue()[:200])


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        test_new_then_rediscovered(tmp)
        test_reads_never_count_as_rediscovery(tmp)
        test_persistence_across_sessions(tmp)
        test_unconsumed_facts_are_advisory_and_loud(tmp)
        test_gap_lifecycle(tmp)
        test_unknown_kind_is_refused(tmp)
        test_corrupt_line_does_not_kill_the_store(tmp)
        test_end_to_end_cap_fact_is_applied_by_task(tmp)

    for line in PASS:
        print(f"  ok    {line}")
    for line in FAIL:
        print(f"  FAIL  {line}")
    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
