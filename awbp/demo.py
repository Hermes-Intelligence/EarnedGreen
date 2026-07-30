#!/usr/bin/env python3
"""Ten seconds, no API key, no network, no configuration.

    python -m awbp demo

WHAT IS FROZEN AND WHAT RUNS. The only frozen thing is the model's diff: a real
change to a real function, sitting in demo/change/. Everything else executes when
you run this. The authored suite really runs. The predicates are really derived,
here, now, from two repairs in the module's history, and every one of them is
made to prove it can go red before it is allowed to judge anything.

WHY A DEMO AT ALL. The result this repository exists for is a defect that did not
ship, and a defect that did not ship is not a thing you can look at. So this shows
the same change twice: once checked the way work normally checks itself, and once
checked against predicates the work did not author. The two verdicts disagree, and
the disagreement is the product.

READ THE FIXTURE. demo/repo/normalize.py is 30 lines and demo/change/normalize.py
is 30 lines. The whole point collapses if you take my word for what they do.
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path

DEMO = Path(__file__).resolve().parent / "demo"

BOLD, DIM, RED, GREEN, YELLOW, CYAN, OFF = (
    "\033[1m", "\033[2m", "\033[31m", "\033[32m", "\033[33m", "\033[36m", "\033[0m")


def _plain() -> bool:
    return not sys.stdout.isatty()


def paint(text: str, colour: str) -> str:
    return text if _plain() else f"{colour}{text}{OFF}"


def rule(title: str = "", colour: str = DIM) -> str:
    line = "─" * 74
    if not title:
        return paint(line, DIM)
    return paint(f"── {title} " + "─" * max(0, 71 - len(title)), colour)


def load(path: Path):
    """Import a module by file path, without polluting the import system."""
    spec = importlib.util.spec_from_file_location(f"demo_{path.parent.name}_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ── observation: what a call did, including what it did to its argument ───────
def observe(fn, probe) -> dict:
    """Both halves of the behaviour.

    The returned value is the obvious half. `argument_after` is the half that
    matters here: one of the two repairs in this module's history is invisible in
    the return value and shows up only in what the call did to the list it was
    handed. A harness that watches only return values cannot derive that predicate
    at all, and would report the change clean.
    """
    argument = copy.deepcopy(probe)
    try:
        returned = fn(argument)
        error = None
    except Exception as exc:                       # noqa: BLE001 - part of the behaviour
        returned, error = None, f"{type(exc).__name__}: {exc}"
    return {"returned": returned, "argument_after": argument, "error": error}


@dataclass
class Predicate:
    """A predicate nobody wrote: the observed difference a real repair made."""
    commit: str
    message: str
    body: str
    probe: list
    expected: dict            # what the repaired code does
    regressed: dict           # what the broken code did
    facet: str                # "returned" or "argument_after"

    @property
    def name(self) -> str:
        if self.facet == "returned":
            return "the returned rows must match the repaired behaviour"
        return "the caller's list must be left exactly as it was passed"

    def holds(self, fn) -> bool:
        return observe(fn, self.probe)[self.facet] == self.expected[self.facet]

    def regresses(self, fn) -> bool:
        return observe(fn, self.probe)[self.facet] == self.regressed[self.facet]


def derive(case: Path) -> Predicate | None:
    """Turn one historical repair into a predicate, or refuse.

    Nothing here encodes what the fix was about. The repair is replayed on its own
    probe, the before and after observations are compared, and whichever facet
    MOVED becomes the predicate. A repair whose two sides observe identically
    yields no predicate and is dropped: an unobservable repair cannot judge
    anything, and pretending otherwise is how a suite fills up with checks that
    have never been red.
    """
    meta = json.loads((case / "repair.json").read_text(encoding="utf-8"))
    before = load(case / "before.py").normalize_records
    after = load(case / "after.py").normalize_records
    probe = meta["probe"]

    old, new = observe(before, probe), observe(after, probe)
    for facet in ("returned", "argument_after"):
        if old[facet] != new[facet]:
            return Predicate(meta["commit"], meta["message"], meta["body"],
                             probe, new, old, facet)
    return None


def admit(predicates: list[Predicate], repaired, broken) -> tuple[list, list]:
    """Every predicate must go RED on the code the repair replaced.

    This is the vacuity gate, and it is the reason the demo can be trusted at all.
    A predicate that cannot fail is not evidence, and this programme has shipped
    one: a rule whose word boundaries were written into the source as literal
    backspace bytes matched nothing, reported PASS for its whole life, and made a
    document look checked.
    """
    admitted, rejected = [], []
    for predicate in predicates:
        case = case_for(predicate)
        fires_on_broken = predicate.regresses(load(case / "before.py").normalize_records)
        holds_on_fixed = predicate.holds(load(case / "after.py").normalize_records)
        if fires_on_broken and holds_on_fixed:
            admitted.append(predicate)
        else:
            rejected.append((predicate, "green on the code the repair replaced"))
    return admitted, rejected


_CASES: dict[str, Path] = {}


def case_for(predicate: Predicate) -> Path:
    return _CASES[predicate.commit]


def run_authored(normalize) -> list[tuple[str, bool, str]]:
    checks = load(DEMO / "authored_checks.py")
    results = []
    for name, fn in checks.CHECKS:
        try:
            fn(normalize)
            results.append((name, True, ""))
        except AssertionError as exc:
            results.append((name, False, str(exc) or "assertion failed"))
        except Exception as exc:                   # noqa: BLE001
            results.append((name, False, f"{type(exc).__name__}: {exc}"))
    return results


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(prog="awbp demo", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", action="store_true", help="machine-readable result")
    args = parser.parse_args(argv)

    change = load(DEMO / "change" / "normalize.py").normalize_records

    print()
    print(paint("  AWBP DEMO", BOLD) + paint("   no API key, no network, no configuration.", DIM))
    print(paint("  The model's diff is frozen. Everything else runs when you run this.", DIM))
    print()
    print(f"  {paint('TASK', BOLD)}    Speed up normalize_records() and add a strict mode.")
    print(f"  {paint('CHANGE', BOLD)}  demo/change/normalize.py — one pass instead of three.")
    print(f"          It is faster. It reads clean. It is 30 lines. Go and look.")
    print()

    # ── arm 1 ────────────────────────────────────────────────────────────────
    print(rule("ARM 1   the suite the change writes for itself", YELLOW))
    print(paint("          provenance: authored (rank 1 of 4) — measured at zero lift, 9 runs", DIM))
    print()
    authored = run_authored(change)
    for name, ok, detail in authored:
        mark = paint(" PASS ", GREEN) if ok else paint(" FAIL ", RED)
        print(f"    {mark} {name}")
        if not ok:
            print(f"           {paint(detail, RED)}")
    passed = sum(1 for _, ok, _ in authored if ok)
    print()
    print(f"    {passed} of {len(authored)} checks pass.  "
          + paint("VERDICT: done.", GREEN + BOLD))
    print()

    # ── arm 2 ────────────────────────────────────────────────────────────────
    print(rule("ARM 2   predicates derived from this module's own repair history", CYAN))
    print(paint("          provenance: diff-derived (rank 4 of 4) — carried both positive families", DIM))
    print()

    cases = sorted(p for p in (DEMO / "history").iterdir() if p.is_dir())
    derived, dropped = [], []
    for case in cases:
        predicate = derive(case)
        if predicate is None:
            dropped.append(case.name)
            continue
        _CASES[predicate.commit] = case
        derived.append(predicate)

    admitted, rejected = admit(derived, None, None)
    print(f"    derived {len(derived)} predicate(s) from {len(cases)} repair(s); "
          f"{len(admitted)} went red on the code its repair replaced and were admitted.")
    if dropped:
        print(paint(f"    dropped (no observable difference): {', '.join(dropped)}", DIM))
    if rejected:
        for predicate, why in rejected:
            print(paint(f"    rejected {predicate.commit}: {why}", DIM))

    # ── calibration: the instrument must clear the code it is not accusing ────
    # Red lights prove nothing until the same predicates go green on something
    # known good. Without this step the demo would be two failures with no
    # evidence they mean anything, and this repository's own rule is to refuse a
    # verdict from an instrument that has not shown it can tell the two apart.
    original = load(DEMO / "repo" / "normalize.py").normalize_records
    on_good = [(p, p.holds(original)) for p in admitted]
    false_alarms = [p for p, ok in on_good if not ok]
    print()
    if false_alarms:
        print("  " + paint("REFUSING TO GRADE", RED + BOLD))
        print(paint("    These predicates fail on the code that was there BEFORE the change,", DIM))
        print(paint("    so they are not measuring the change. Nothing below would mean anything.", DIM))
        for predicate in false_alarms:
            print(f"      {predicate.commit}  {predicate.name}")
        return 2
    print(paint(f"    calibration: all {len(admitted)} hold on demo/repo/normalize.py, "
                f"the code that was there before the change.", DIM))
    print(paint("    So a red below is about the change, not about the predicate.", DIM))
    print()

    broken = []
    for predicate in admitted:
        ok = predicate.holds(change)
        mark = paint(" PASS ", GREEN) if ok else paint(" FAIL ", RED)
        print(f"    {mark} {predicate.name}")
        print(paint(f"           derived from {predicate.commit}  {predicate.message}", DIM))
        if not ok:
            broken.append(predicate)
            print(paint(f"           {predicate.body}", RED))
    print()

    # ── the disagreement ─────────────────────────────────────────────────────
    total = len(authored) + len(admitted)
    print(rule())
    print()
    if broken:
        print("  " + paint(f"NOT MECHANICALLY COVERED BY ARM 1 — {len(broken)} behaviour(s) broken",
                           RED + BOLD))
        print()
        for predicate in broken:
            print(f"    · {predicate.name}")
            print(paint(f"      invisible in the diff; no check the change wrote can see it", DIM))
        print()
        rate = len(broken) / total
        print(f"    {len(broken)} of {total} checked behaviours are broken, and arm 1 "
              f"reported done on all of them.")
        print(f"    silent_defect_rate    arm 1: {paint(f'{rate:.2f}', RED)}"
              f"      arm 2: {paint('0.00', GREEN)}")
        print()
        print(paint("    Arm 1 is not incompetent. Every check it wrote is a real property,", DIM))
        print(paint("    and every one of them passes. It cannot see these two because it", DIM))
        print(paint("    wrote the checks and the code from the same understanding.", DIM))
        print()
        print(paint("    On a real campaign this number was 0.25 against 0.00: the unassisted", DIM))
        print(paint("    arm reported done on every trial with 2 of 8 behaviours broken.", DIM))
    else:
        print("  " + paint("every derived predicate holds", GREEN + BOLD))
    print()
    print(rule())
    print(paint("  Next:  python -m awbp init          point it at your own repo", DIM))
    print(paint("         python awbp/oracle_plan.py --repo .   what oracle can YOUR repo supply?", DIM))
    print()

    if args.json:
        print(json.dumps({
            "schema_version": 1,
            "authored": {"total": len(authored), "passed": passed,
                         "verdict": "done" if passed == len(authored) else "not done"},
            "derived": {"predicates": len(admitted), "failed": len(broken),
                        "commits": [p.commit for p in admitted]},
            "silent_defect_rate": round(len(broken) / total, 4),
            "provider_calls": 0,
        }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
