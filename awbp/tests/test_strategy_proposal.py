#!/usr/bin/env python3
"""The environment proposes a working method; a human never has to type one.

The owner's requirement: the environment decides what to switch on from what the
task is, and the decision is recorded so it can be correlated with the outcome.

Two things are asserted here and they pull against each other on purpose.

The proposal must be USEFUL: a mechanical task in a repo with a rank-4 oracle
should not pay for a reviewer, and a client-facing document with no mechanical
oracle should always get one.

The proposal must also be HONEST about its own basis: one task, one trial per
arm. It carries `confidence: low`, it never proposes `council` (never run, and
the external evidence on panels is 17.2x error amplification), and an explicit
choice always beats it.

    python tests/test_strategy_proposal.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import execution_strategy as es          # noqa: E402

PASS, FAIL = [], []


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASS if condition else FAIL).append(f"{name}{' — ' + detail if detail else ''}")


def test_a_strong_oracle_argues_for_solo() -> None:
    result = es.propose("rename the helper and fix the failing test",
                        oracle_verdict="STRONG", risk="low",
                        available_sources=["repo-tests", "diff-derived"])
    check("mechanical work with a rank-4 oracle proposes solo",
          result["proposed"] == "solo", result["proposed"])
    check("and says why", any("rank-4" in s for s in result["signals"]))


def test_a_weak_oracle_plus_judgement_argues_for_review() -> None:
    result = es.propose(
        "write a client-facing one-pager, follow the brand book, beautifully typeset",
        oracle_verdict="WEAK", available_sources=["spec"])
    check("judgement work with no mechanical oracle proposes reviewed",
          result["proposed"] == "reviewed", result["proposed"])
    check("names the WEAK oracle as the reason",
          any("WEAK" in s for s in result["signals"]), str(result["signals"]))


def test_consequence_is_a_floor_not_a_vote() -> None:
    """Irreversible work never drops to solo, however strong the oracle is."""
    result = es.propose(
        "add a migration that backfills the customer billing column in production",
        oracle_verdict="STRONG", risk="high",
        available_sources=["repo-tests", "data"])
    check("irreversible production work never proposes solo",
          result["proposed"] != "solo", result["proposed"])
    check("the floor is stated, not silent",
          any("floor" in s for s in result["signals"]), str(result["signals"]))


def test_high_risk_alone_raises_the_floor() -> None:
    result = es.propose("tidy up the imports", oracle_verdict="STRONG", risk="critical",
                        available_sources=["repo-tests"])
    check("critical risk never proposes solo", result["proposed"] != "solo",
          result["proposed"])


def test_whole_words_only() -> None:
    """`product` is not `production`, and the first version could not tell.

    Substring matching produced a confident wrong answer three separate times in
    this repository in one day. Every vocabulary in it now matches tokens.
    """
    result = es.propose("add a product field to the catalogue table",
                        oracle_verdict="STRONG", available_sources=["repo-tests"])
    check("'product' does not read as production work",
          not any("expensive or hard to reverse" in s for s in result["signals"]),
          str(result["signals"]))
    check("and the proposal is therefore solo", result["proposed"] == "solo",
          result["proposed"])

    real = es.propose("deploy to production", oracle_verdict="STRONG",
                      available_sources=["repo-tests"])
    check("but real production work still registers",
          any("expensive or hard to reverse" in s for s in real["signals"]),
          str(real["signals"]))


def test_council_is_never_proposed() -> None:
    """An unmeasured, expensive mechanism must not arrive by default."""
    tasks = [
        ("redesign the whole public architecture and delete the legacy billing path",
         "WEAK", ["spec"], "critical"),
        ("write a client proposal", "WEAK", ["spec"], "high"),
        ("publish the customer-facing security document", "WEAK", ["spec"], "critical"),
    ]
    for task, verdict, sources, risk in tasks:
        result = es.propose(task, oracle_verdict=verdict, risk=risk,
                            available_sources=sources)
        check(f"council not proposed for: {task[:38]}...",
              result["proposed"] != "council", result["proposed"])
    check("but the reason council is withheld is stated",
          "17.2x" in es.propose("x")["council_note"])


def test_the_proposal_admits_what_it_rests_on() -> None:
    result = es.propose("write a report", oracle_verdict="WEAK", available_sources=["spec"])
    check("confidence is low", result["confidence"] == "low")
    # Updated after family J: the proposal's pick won zero measured axes, and
    # the basis must now carry that measured humility rather than the old
    # sample-size caveat.
    check("the basis names its measured humiliation",
          "ZERO" in result["basis"] and "family" in result["basis"],
          result["basis"][:80])
    check("a reason is generated that survives the declaration gate",
          len(result["reason"].split()) >= es.REQUIRED_REASON_WORDS,
          result["reason"])


def test_the_generated_reason_is_accepted_by_declare() -> None:
    """The proposal has to clear the same bar a human's reason does."""
    for task, verdict, sources in (
            ("rename a helper", "STRONG", ["repo-tests"]),
            ("write a client one-pager", "WEAK", ["spec"]),
            ("", "", [])):
        result = es.propose(task, oracle_verdict=verdict, available_sources=sources)
        try:
            record = es.declare(result["proposed"], result["reason"], "medium")
            check(f"declare accepts the generated reason for {result['proposed']!r}",
                  record["strategy"] == result["proposed"])
        except ValueError as exc:
            check(f"declare accepts the generated reason for {task[:24]!r}", False, str(exc))


def test_an_empty_task_still_proposes_something_defensible() -> None:
    result = es.propose("")
    check("an empty task does not crash", result["proposed"] in es.STRATEGIES)
    check("an empty task does not silently pick the cheapest",
          result["proposed"] != "council")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    test_a_strong_oracle_argues_for_solo()
    test_a_weak_oracle_plus_judgement_argues_for_review()
    test_consequence_is_a_floor_not_a_vote()
    test_high_risk_alone_raises_the_floor()
    test_whole_words_only()
    test_council_is_never_proposed()
    test_the_proposal_admits_what_it_rests_on()
    test_the_generated_reason_is_accepted_by_declare()
    test_an_empty_task_still_proposes_something_defensible()

    for line in PASS:
        print(f"  ok    {line}")
    for line in FAIL:
        print(f"  FAIL  {line}")
    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
