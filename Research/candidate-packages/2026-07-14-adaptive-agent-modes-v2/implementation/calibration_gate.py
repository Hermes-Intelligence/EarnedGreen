#!/usr/bin/env python3
"""Calibration as a PRECONDITION of grading, not a ritual performed once.

Every wrong number this programme ever produced came from the instrument, not
from the work. Four of them, all in front of me, all plausible:

  1. playwright resolves routes last-registered-first; a catch-all registered
     after the specific stubs shadowed them. Every arm read as "no board".
     That single defect was the whole 65% -> 86% swing.
  2. `VITE_API_BASE_URL` was not passed to the build, so the app threw at load
     and every arm would have scored a clean, believable ZERO.
  3. A shell rewrote `/api` into a Windows path inside the build environment,
     so the bundle shipped a silently wrong API base.
  4. A layout predicate written to catch a visible clipping bug came back GREEN
     on the build that had it — twice, for two different reasons.

Three of the four produce numbers you would happily report. That is the danger:
a broken instrument does not announce itself, it just agrees with you.

The fix costs seconds. Before grading anything, grade the two fixtures whose
answers are already known — the known-GOOD build and the known-HOLLOW one — and
if the instrument cannot tell them apart, REFUSE TO GRADE. An instrument that
cannot separate a real implementation from a deliberate fake has no business
producing a score for anything else.

Usage as a library:

    gate = CalibrationGate(bands={"good": (0.8, 1.0), "hollow": (0.0, 0.35)})
    verdict = gate.check(good_score=0.94, hollow_score=0.10)
    if not verdict.may_grade:
        raise SystemExit(verdict.report())

Usage as a CLI (scores from a prior run, or a command per fixture):

    python calibration_gate.py --good 0.94 --hollow 0.10
    python calibration_gate.py --config calibration.json
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

# Defaults chosen to be permissive: this gate exists to catch an instrument that
# is BROKEN, not to enforce a quality bar. A good fixture scoring 0.7 is a weak
# instrument; a good fixture scoring 0.0 is a broken one, and only the second is
# this gate's business.
DEFAULT_BANDS: dict[str, tuple[float, float]] = {
    "good": (0.70, 1.00),
    "hollow": (0.00, 0.40),
}

# The two fixtures must also be SEPARATED, not merely inside their bands.
#
# Under the DEFAULT bands this is redundant and deliberately so: good >= 0.70 and
# hollow <= 0.40 already force a gap of at least 0.30, so the separation check
# cannot fire and is not meant to. It exists for callers who register LOOSER
# bands — e.g. an instrument whose good fixture only reaches 0.55 — where the two
# bands overlap enough that both can pass while the instrument separates nothing.
# Stated because a check that can never fire under its own defaults reads like a
# guarantee and is not one.
DEFAULT_MIN_SEPARATION = 0.25


@dataclass
class CalibrationVerdict:
    may_grade: bool
    good_score: float
    hollow_score: float
    separation: float
    failures: list[str] = field(default_factory=list)
    bands: dict[str, tuple[float, float]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "may_grade": self.may_grade,
            "good_score": self.good_score,
            "hollow_score": self.hollow_score,
            "separation": round(self.separation, 4),
            "failures": list(self.failures),
            "bands": {k: list(v) for k, v in self.bands.items()},
        }

    def report(self) -> str:
        if self.may_grade:
            return (f"calibration OK — good={self.good_score:.3f} "
                    f"hollow={self.hollow_score:.3f} separation={self.separation:.3f}; "
                    f"grading may proceed")
        lines = ["REFUSING TO GRADE — the instrument failed its own calibration.",
                 f"  known-good fixture:   {self.good_score:.3f}",
                 f"  known-hollow fixture: {self.hollow_score:.3f}",
                 f"  separation:           {self.separation:.3f}"]
        for failure in self.failures:
            lines.append(f"  ! {failure}")
        lines.append("  Any score this instrument produces right now is unreliable, including")
        lines.append("  a score that looks entirely reasonable. Fix the harness, then grade.")
        return "\n".join(lines)


class CalibrationGate:
    """Refuses to let grading proceed unless the instrument still discriminates."""

    def __init__(self, bands: dict[str, tuple[float, float]] | None = None,
                 min_separation: float = DEFAULT_MIN_SEPARATION) -> None:
        self.bands = dict(bands or DEFAULT_BANDS)
        for name in ("good", "hollow"):
            if name not in self.bands:
                raise ValueError(f"bands must register a {name!r} range")
        self.min_separation = float(min_separation)

    def check(self, good_score: float, hollow_score: float) -> CalibrationVerdict:
        failures: list[str] = []
        good_lo, good_hi = self.bands["good"]
        hollow_lo, hollow_hi = self.bands["hollow"]

        if not (good_lo <= good_score <= good_hi):
            failures.append(
                f"the known-GOOD fixture scored {good_score:.3f}, outside its registered "
                f"band [{good_lo:.2f}, {good_hi:.2f}] — the instrument is failing work "
                f"that is known to be correct")
        if not (hollow_lo <= hollow_score <= hollow_hi):
            failures.append(
                f"the known-HOLLOW fixture scored {hollow_score:.3f}, outside its registered "
                f"band [{hollow_lo:.2f}, {hollow_hi:.2f}] — the instrument is passing a "
                f"deliberate fake, so it would pass a real one too")
        separation = good_score - hollow_score
        if separation < self.min_separation:
            failures.append(
                f"good and hollow are only {separation:.3f} apart (need "
                f"{self.min_separation:.2f}) — whatever this measures, it is not the "
                f"difference between real work and a fake")
        return CalibrationVerdict(may_grade=not failures, good_score=good_score,
                                  hollow_score=hollow_score, separation=separation,
                                  failures=failures, bands=self.bands)

    def guard(self, grade_fixture: Callable[[str], float]) -> CalibrationVerdict:
        """Score both fixtures through the caller's own grader and judge the result.

        `grade_fixture` receives "good" / "hollow" and returns that fixture's score
        using the SAME path the real grading will take — a calibration run through
        a different code path proves nothing about the path that matters.
        """
        return self.check(good_score=float(grade_fixture("good")),
                          hollow_score=float(grade_fixture("hollow")))


def require_calibration(good_score: float, hollow_score: float,
                        bands: dict[str, tuple[float, float]] | None = None,
                        min_separation: float = DEFAULT_MIN_SEPARATION) -> CalibrationVerdict:
    """Convenience wrapper: raises RuntimeError when grading must not proceed."""
    verdict = CalibrationGate(bands, min_separation).check(good_score, hollow_score)
    if not verdict.may_grade:
        raise RuntimeError(verdict.report())
    return verdict


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(
        description="Refuse to grade unless the instrument still separates good from hollow.")
    parser.add_argument("--good", type=float, help="score of the known-good fixture")
    parser.add_argument("--hollow", type=float, help="score of the known-hollow fixture")
    parser.add_argument("--config", type=Path,
                        help="JSON: {good, hollow, bands?:{good:[lo,hi],hollow:[lo,hi]}, min_separation?}")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    payload: dict[str, Any] = {}
    if args.config:
        payload = json.loads(args.config.read_text(encoding="utf-8-sig"))
    good = args.good if args.good is not None else payload.get("good")
    hollow = args.hollow if args.hollow is not None else payload.get("hollow")
    if good is None or hollow is None:
        parser.error("both --good and --hollow are required (directly or via --config)")

    bands = payload.get("bands")
    bands = {k: tuple(v) for k, v in bands.items()} if bands else None
    gate = CalibrationGate(bands, payload.get("min_separation", DEFAULT_MIN_SEPARATION))
    verdict = gate.check(float(good), float(hollow))
    if args.output:
        args.output.write_text(json.dumps(verdict.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(verdict.report())
    raise SystemExit(0 if verdict.may_grade else 2)


if __name__ == "__main__":
    main()
