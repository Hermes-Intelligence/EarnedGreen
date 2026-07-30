#!/usr/bin/env python3
"""The demo is a claim made to strangers, so it is tested like one.

A shop window that quietly stops showing the defect is worse than no shop window:
it still says "look what we catch" while catching nothing. Every assertion below
fails loudly if someone edits the fixture until the demonstration stops
demonstrating.

The load-bearing one is `test_predicates_are_not_written_by_hand`. The demo's
whole claim is that nobody authored these predicates: they are the observed
difference two real repairs made. If the derivation ever starts returning
something that does not come from replaying before.py against after.py, the demo
becomes theatre and this test is what says so.

    python tests/test_demo.py
"""
from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import demo                 # noqa: E402

PASS, FAIL = [], []


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASS if condition else FAIL).append(f"{name}{' — ' + detail if detail else ''}")


def _load(rel: str):
    return demo.load(demo.DEMO / rel).normalize_records


def test_authored_suite_is_green_on_the_change() -> None:
    """If the change ever fails a check it wrote itself, the demo has no point."""
    results = demo.run_authored(_load("change/normalize.py"))
    failures = [name for name, ok, _ in results if not ok]
    check("the change passes every check it wrote for itself", not failures, str(failures))
    check("the authored suite is not trivially small", len(results) >= 6, str(len(results)))


def test_authored_suite_is_green_on_the_original() -> None:
    """The authored checks are real properties, not accidents of the rewrite."""
    results = demo.run_authored(_load("repo/normalize.py"))
    failures = [name for name, ok, _ in results if not ok]
    check("the authored suite also passes on the pre-change code", not failures, str(failures))


def test_predicates_are_not_written_by_hand() -> None:
    """Derivation must read the repair, not a stored answer."""
    cases = sorted(p for p in (demo.DEMO / "history").iterdir() if p.is_dir())
    check("history has repairs to derive from", len(cases) >= 2, str(len(cases)))

    for case in cases:
        predicate = demo.derive(case)
        check(f"{case.name}: yields a predicate", predicate is not None)
        if predicate is None:
            continue
        demo._CASES[predicate.commit] = case
        before = demo.load(case / "before.py").normalize_records
        after = demo.load(case / "after.py").normalize_records
        # The expectation must BE the repaired behaviour, observed, not asserted.
        check(f"{case.name}: expectation equals what after.py actually does",
              predicate.holds(after))
        check(f"{case.name}: predicate goes RED on the code the repair replaced",
              not predicate.holds(before))


def test_the_two_defects_are_invisible_to_the_authored_suite() -> None:
    """The disagreement is the product. Both halves of it are asserted here."""
    change = _load("change/normalize.py")
    cases = sorted(p for p in (demo.DEMO / "history").iterdir() if p.is_dir())
    predicates = [p for p in (demo.derive(c) for c in cases) if p]
    for predicate, case in zip(predicates, cases):
        demo._CASES[predicate.commit] = case

    broken = [p for p in predicates if not p.holds(change)]
    check("exactly two derived predicates fail on the change", len(broken) == 2,
          f"{len(broken)} failed")

    facets = sorted(p.facet for p in broken)
    check("one defect is in the return value and one only in the caller's list",
          facets == ["argument_after", "returned"], str(facets))


def test_calibration_holds_on_the_pre_change_code() -> None:
    """Red lights mean nothing until the same predicates go green on known-good code."""
    original = _load("repo/normalize.py")
    cases = sorted(p for p in (demo.DEMO / "history").iterdir() if p.is_dir())
    predicates = [p for p in (demo.derive(c) for c in cases) if p]
    false_alarms = [p.commit for p in predicates if not p.holds(original)]
    check("no predicate accuses the code that was there before the change",
          not false_alarms, str(false_alarms))


def test_demo_runs_clean_and_reports_the_defects() -> None:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = demo.main([])
    output = buffer.getvalue()
    check("demo exits 0", code == 0, f"exit {code}")
    check("demo says arm 1 is done", "VERDICT: done." in output)
    check("demo opens the finding with what is NOT covered",
          "NOT MECHANICALLY COVERED" in output)
    check("demo names both repairs", "a1b2c3d" in output and "e4f5a6b" in output)
    check("demo states the calibration step", "calibration:" in output)
    check("demo makes no provider call claim it cannot keep",
          "no API key" in output and "no network" in output)


def test_json_output_is_machine_readable() -> None:
    import json
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        demo.main(["--json"])
    payload = json.loads(buffer.getvalue()[buffer.getvalue().index("{"):])
    check("json reports zero provider calls", payload["provider_calls"] == 0)
    check("json reports arm 1 as done", payload["authored"]["verdict"] == "done")
    check("json reports two derived failures", payload["derived"]["failed"] == 2)
    check("json silent_defect_rate is above zero", payload["silent_defect_rate"] > 0,
          str(payload["silent_defect_rate"]))


def test_probe_refuses_an_empty_diff() -> None:
    """A probe over nothing is not a pass.

    `earned = not uncovered` is vacuously true on an empty change, so an untouched
    workspace printed EARNED. That is this repository's own headline defect,
    committed by this repository's own tool, on the path the README sends a
    stranger down. Found by running the README rather than reading it.
    """
    import necessity_probe
    # A REAL suite. The first version of this test passed an empty one, so it hit
    # the older "no behavioural check" guard and never reached the code it was
    # written to cover. It reported a failure that was its own.
    suite = {"checks": [{"id": "c1", "kind": "acceptance", "command": ["true"]}]}
    identical = necessity_probe.probe(
        suite=suite,
        baseline_dir=demo.DEMO / "repo",
        workspace=demo.DEMO / "repo",          # identical: no change at all
    )
    check("empty diff does not report earned", identical["earned"] is False)
    check("empty diff is named, not scored", identical.get("nothing_to_probe") is True,
          str(identical.get("problem") or identical.get("reason", ""))[:70])
    check("empty diff explains itself",
          "NOT a pass" in identical.get("reason", ""), identical.get("reason", "")[:60])

    # And the older guard still fires for its own reason, which is a different one.
    no_checks = necessity_probe.probe(suite={"checks": []},
                                      baseline_dir=demo.DEMO / "repo",
                                      workspace=demo.DEMO / "repo")
    check("a suite with no behavioural check is refused for its own reason",
          "no behavioural check" in no_checks.get("problem", ""),
          no_checks.get("problem", "")[:60])


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    test_authored_suite_is_green_on_the_change()
    test_authored_suite_is_green_on_the_original()
    test_predicates_are_not_written_by_hand()
    test_the_two_defects_are_invisible_to_the_authored_suite()
    test_calibration_holds_on_the_pre_change_code()
    test_demo_runs_clean_and_reports_the_defects()
    test_json_output_is_machine_readable()
    test_probe_refuses_an_empty_diff()

    for line in PASS:
        print(f"  ok    {line}")
    for line in FAIL:
        print(f"  FAIL  {line}")
    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
