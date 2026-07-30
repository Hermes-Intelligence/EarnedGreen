#!/usr/bin/env python3
"""Hygiene for the thing doing the measuring, not for the thing being measured.

On 2026-07-21 a single day's work produced THIRTEEN defects in instruments and
none in the work they were grading. Three of the thirteen produced entirely
plausible numbers, which is the dangerous kind. Two mechanisms would have caught
most of them, and both are here.

  selftest(rules)   Every predicate must prove it can still go RED. One rule in
                    that day's checker had its word boundaries written into the
                    source as literal backspace bytes by a careless patch script.
                    It then searched for a character no document contains, matched
                    nothing, and reported PASS for its whole life. A predicate that
                    cannot fire is worse than no predicate: it makes a document
                    look checked.

  Fingerprint       Before/after evidence that a run only READ from a store. An
                    instruction to read only is not enforcement. That day's first
                    fingerprint also had to learn two things the hard way: a
                    continuously-ingesting table cannot use "row count unchanged"
                    as a write detector, and evidence must be write-once, because
                    a slow background job overwrote the `before` file eight minutes
                    AFTER the comparison had been made with it.

    python instrument_hygiene.py --selftest-demo
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence


# ── 1. Predicates must prove they can fire ────────────────────────────────────
@dataclass
class Rule:
    """A predicate plus an example it MUST match. The example is not documentation."""
    name: str
    matches: Callable[[str], int]
    budget: int = 0
    must_fire_on: str = ""
    why: str = ""


def rule_from_pattern(name: str, pattern: str, must_fire_on: str, budget: int = 0,
                      flags: int = 0, why: str = "") -> Rule:
    return Rule(name=name, matches=lambda text: len(re.findall(pattern, text, flags)),
                budget=budget, must_fire_on=must_fire_on, why=why)


def selftest(rules: Sequence[Rule]) -> dict:
    """Every rule fires on its own example, or it is reported DEAD."""
    rows = []
    for rule in rules:
        if not rule.must_fire_on:
            rows.append({"rule": rule.name, "status": "NO-EXAMPLE",
                         "detail": "the rule carries no example, so nothing proves it can fire"})
            continue
        hits = rule.matches(rule.must_fire_on)
        rows.append({"rule": rule.name,
                     "status": "OK" if hits else "DEAD",
                     "detail": f"{hits} match(es) on its own example"})
    dead = [r for r in rows if r["status"] != "OK"]
    return {"schema_version": 1, "rules": rows, "dead": [r["rule"] for r in dead],
            "usable": not dead,
            "rule": "a predicate that cannot go red has never checked anything"}


def evaluate(rules: Sequence[Rule], text: str) -> dict:
    """Run the rules, but ONLY after proving they can fire."""
    health = selftest(rules)
    if not health["usable"]:
        return {"graded": False, "reason": "dead predicates: " + ", ".join(health["dead"]),
                "selftest": health}
    findings = []
    for rule in rules:
        hits = rule.matches(text)
        findings.append({"rule": rule.name, "hits": hits, "budget": rule.budget,
                         "ok": hits <= rule.budget,
                         "why": "" if hits <= rule.budget else rule.why})
    return {"graded": True, "selftest": health, "findings": findings,
            "failed": [f["rule"] for f in findings if not f["ok"]]}


# ── 2. Read-only, proven rather than promised ─────────────────────────────────
@dataclass
class Fingerprint:
    """Before/after evidence over a set of named counters.

    `live` names counters fed by a continuously-running pipeline. Those are
    compared with a tolerance and a note, never for equality: on that day the
    central-bank feed ingested one genuine speech mid-run and a strict comparison
    called it a write by the agent.
    """
    counters: dict[str, int] = field(default_factory=dict)
    live: set[str] = field(default_factory=set)

    @staticmethod
    def capture(probes: dict[str, Callable[[], int]], live: Sequence[str] = ()) -> "Fingerprint":
        return Fingerprint({name: int(fn()) for name, fn in probes.items()}, set(live))

    def write(self, path: Path) -> None:
        # WRITE-ONCE. Evidence that can be clobbered is not evidence.
        if path.exists():
            raise FileExistsError(
                f"{path.name} already exists. A fingerprint is written once; move or delete "
                f"the existing file deliberately if you mean to replace it.")
        path.write_text(json.dumps({"counters": self.counters, "live": sorted(self.live)},
                                   indent=2) + "\n", encoding="utf-8")

    @staticmethod
    def read(path: Path) -> "Fingerprint":
        data = json.loads(path.read_text(encoding="utf-8"))
        return Fingerprint(data["counters"], set(data.get("live", [])))

    def compare(self, after: "Fingerprint", live_tolerance: float = 0.01) -> dict:
        drift, tolerated = [], []
        for name, before in self.counters.items():
            now = after.counters.get(name)
            if now is None or now == before:
                continue
            if name in self.live and before and abs(now - before) / before <= live_tolerance:
                tolerated.append(f"{name}: {before} -> {now} (live source, within "
                                 f"{live_tolerance:.0%}; inspect the new rows before accepting)")
            else:
                drift.append(f"{name}: {before} -> {now}")
        return {
            "read_only": not drift,
            "drift": drift,
            "tolerated_live_drift": tolerated,
            "rule": ("a counter that moved is a question, not a verdict: look at WHAT changed "
                     "before calling it a write. A live pipeline ingesting its own data is not "
                     "the agent writing."),
        }


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest-demo", action="store_true")
    args = parser.parse_args()
    if not args.selftest_demo:
        print(__doc__)
        raise SystemExit(0)

    rules = [
        rule_from_pattern("em-dash", "—", "a sentence — like this", 0,
                          why="the most recognisable machine-writing tell"),
        # the exact shape of the defect: word boundaries as literal backspace bytes
        rule_from_pattern("dead-rule", "\x08[a-z]+\x08", "nothing can contain this", 0,
                          why="this rule is dead and must be reported as such"),
    ]
    health = selftest(rules)
    for row in health["rules"]:
        print(f"  {row['status']:<10}{row['rule']:<16}{row['detail']}")
    print()
    print("usable:", health["usable"], "| dead:", health["dead"])
    result = evaluate(rules, "some text — with a dash")
    print("graded:", result["graded"], "|", result.get("reason", ""))
    raise SystemExit(0 if health["usable"] else 1)


if __name__ == "__main__":
    main()
