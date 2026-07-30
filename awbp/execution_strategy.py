#!/usr/bin/env python3
"""How this task will be EXECUTED: declared by the agent at task start, recorded.

The mode ladder answers "how much ceremony does this task need". This answers a
different question the ladder never asked: **who does the work, and who checks
it** — one model alone, a cheap model with a strong reviewer, or a strong model
with an adversarial council.

WHY IT IS DECLARED AND NOT DEFAULTED. A measured result on 2026-07-21, one task,
one trial per arm: the same client deliverable produced by Opus alone, by Opus
with a mechanical checker in a forcing loop, and by Sonnet with forced independent
review. The Sonnet arm produced the best-formatted document at 52% of the cost
and dropped three of four checkable figures. There is no single winner, so a
default would be a guess dressed as a policy.

WHY IT IS RECORDED. An agent choosing its own working method is provenance
`authored`, the rung this programme has measured at zero three times. A choice
that is written down with its reason can later be correlated with the outcome;
a choice made silently cannot. This module does not make the choice better. It
makes it checkable.

    python execution_strategy.py --list
    python execution_strategy.py --declare reviewed --reason "..." --out .agentic/
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Each strategy names the capability PROFILES it runs on. Profiles resolve to
# concrete models through Models/providers.json, so a strategy never hard-codes
# a model name and cannot rot when the catalogue changes.
STRATEGIES = {
    "solo": {
        "rank": 0,
        "executor_profile": "balanced-daily",
        "reviewer_profile": None,
        "council_profiles": [],
        "purpose": "One model does the work and checks its own output against the "
                   "task's mechanical checks. The cheapest path and the right one "
                   "when the checks are strong enough to catch what matters.",
        "choose_when": [
            "the task has a mechanical oracle that already covers what could go wrong",
            "the work is narrow and its failure modes are visible in the checks",
            "the deliverable is internal and cheap to redo",
        ],
        "measured": "the default. Bare vanilla beat nothing and lost to nothing on "
                    "the 2026-07-21 deliverable; on two hard families it lost to a "
                    "forcing loop by 55 and 28 points.",
    },
    "reviewed": {
        "rank": 1,
        "executor_profile": "balanced-daily",
        "reviewer_profile": "adversarial-review",
        "council_profiles": [],
        "purpose": "A cheaper model does the work; a stronger one reviews it with "
                   "fresh context and a brief to find a specific class of failure. "
                   "Buys review at a fraction of the cost of running everything on "
                   "the expensive model.",
        "choose_when": [
            "craft matters and the failure modes are ones a reader can see",
            "the budget matters and the task is long",
            "an independent pass is worth more than a stronger first draft",
        ],
        "measured": "TWO measurements now. (1) one doc task, one trial: best format "
                    "at 52% cost, three of four figures dropped. (2) family J, 3 "
                    "trials: the WORST arm of the campaign - fewest real bindings, "
                    "most fabricated endpoints (6.3 mean, worst single artifact: 0 "
                    "bound / 17 invented), at 2.8x solo cost. A stronger reviewer "
                    "did not reliably stop a cheaper executor from inventing.",
    },
    "council": {
        "rank": 2,
        "executor_profile": "architecture-high-risk",
        "reviewer_profile": "adversarial-review",
        "council_profiles": ["architecture-high-risk", "creative-design"],
        "purpose": "A strong model does the work, a strong reviewer attacks it, AND an "
                   "independent council reads it from different angles. Note the stack: "
                   "council always INCLUDES the reviewer; they are layers, not "
                   "alternatives.",
        "choose_when": [
            "the blast radius is large and a defect is expensive to reverse",
            "the task is genuinely underspecified and the design space is wide",
            "an outward-facing action is involved",
        ],
        "measured": "UNMEASURED as a correctness mechanism. External evidence puts "
                    "multi-agent error amplification at 17.2x when independent and "
                    "~4.4x when centralised, at roughly 7x the tokens. Choose it for "
                    "blast radius, not for quality.",
    },
    # The owner's original dg-d design, never yet run: EVERYTHING AT ONCE on a
    # cheap base. The environment must be able to stack supporter and verifier
    # simultaneously — they are orthogonal roles, not rungs of a ladder. `full`
    # differs from `council` in exactly one place (the executor tier), so in a
    # benchmark full-vs-reviewed isolates the support stack's contribution and
    # full-vs-council isolates the executor tier's. That factoring is what makes
    # the combination measurable instead of just impressive.
    "full": {
        "rank": 3,
        "executor_profile": "balanced-daily",
        "reviewer_profile": "adversarial-review",
        "council_profiles": ["creative-design", "creative-design"],
        "purpose": "A cheap model does the work while BOTH support layers run: a strong "
                   "adversarial reviewer AND an independent council (two passes of the "
                   "creative profile under different briefs). The bet: the support stack "
                   "recovers more than the cheap executor gives up.",
        "choose_when": [
            "judgement work where independent eyes are the only oracle available",
            "the task is long enough that the executor-tier saving is real",
            "you want the full environment exercised, not a subset",
        ],
        "measured": "family J, 3 trials (first flight, telemetry-confirmed): "
                    "consistently better than `reviewed` (2.0 vs 6.3 mean invented "
                    "endpoints, best mobile coverage, best single artifact of the "
                    "campaign) at 3.5x solo cost - and did NOT beat frontier-solo "
                    "on wiring depth or craft, nor cheap-solo on honesty (0.0 "
                    "invented). Expensive insurance with a real but partial payout.",
    },
}

REQUIRED_REASON_WORDS = 8


# ── proposing a strategy from the task and the repository ─────────────────────
#
# The owner's requirement, and the right one: the environment decides, the human
# does not type it. What follows is a PROPOSAL with its reasoning shown, not a
# verdict, and it says so in its own output — because the evidence behind it is
# one task and one trial per arm, which is not enough to justify a silent policy.
#
# The signals are read from the task text and from what oracle_plan already found
# out about the repository. Nothing here asks a model anything.

# MATCHED AS WHOLE WORDS, NEVER SUBSTRINGS. The first version of this list used
# `in text` and read "product pack" as production work, because "prod" is inside
# "product". That is the third time in one day that substring matching produced a
# confident wrong answer in this repository, after `latest-brief.ts` and
# `spec_synthesis.py` were read as test files.
_CONSEQUENCE = ("production", "prod", "customer", "customers", "client", "clients",
                "public", "publish", "deploy", "deployment", "migration", "migrate",
                "billing", "payment", "payments", "invoice", "credential",
                "credentials", "secret", "secrets", "auth", "security", "delete",
                "drop", "irreversible", "send", "email")

# Words that mark work with taste in it: many valid answers, no mechanical oracle
# for which one is good. This is where an independent second opinion has the most
# room to help and where a checker has the least.
_JUDGEMENT = ("design", "brand", "copy", "wording", "tone", "layout", "typography",
              "document", "deliverable", "pitch", "proposal", "report", "one-pager",
              "readme", "naming", "architecture", "trade-off", "tradeoff", "strategy")

# Words that mark narrow mechanical work, where the checks do the catching.
_MECHANICAL = ("rename", "typo", "bump", "lint", "format", "refactor", "extract",
               "inline", "test", "fix", "patch", "add a field", "add a column")


def propose(task: str, oracle_verdict: str = "", risk: str = "medium",
            available_sources: list[str] | None = None) -> dict:
    """Which strategy this task argues for, with the argument attached.

    The shape of the reasoning, which matters more than the thresholds:

      A STRONG ORACLE ARGUES FOR SOLO. When the repository can supply rank-4
      predicates, the checks catch what matters and a reviewer is paying for
      something already covered. The two positive families ran this way.

      A WEAK ORACLE PLUS JUDGEMENT ARGUES FOR REVIEW. When nothing mechanical can
      say whether the output is good — a client document, a design, a name — the
      only independent signal available is another model looking at it. This is
      also the one case where the measured evidence points anywhere: the reviewed
      arm produced the best-formatted deliverable at 52% of the cost.

      CONSEQUENCE RAISES, IT DOES NOT DECIDE. Irreversible or outward-facing work
      never drops below `reviewed`, whatever the other signals say.
    """
    text = (task or "").lower()
    tokens = set(re.findall(r"[a-z][a-z0-9'-]*", text))
    words = len(text.split())
    sources = set(available_sources or [])

    def present(vocabulary: tuple[str, ...]) -> list[str]:
        """Whole words only, and multi-word entries matched as phrases."""
        hits = set()
        for entry in vocabulary:
            if " " in entry:
                if entry in text:
                    hits.add(entry)
            elif entry in tokens:
                hits.add(entry)
        return sorted(hits)

    signals: list[str] = []
    score = 0                       # negative argues solo, positive argues review

    strong_oracle = bool(sources & {"diff-derived", "data", "repo-tests"})
    if strong_oracle:
        score -= 2
        signals.append("the repository can supply a rank-4 oracle, so mechanical "
                       "checks can catch what matters")
    elif oracle_verdict == "WEAK":
        score += 2
        signals.append("the oracle plan came back WEAK, so no check will tell you "
                       "whether this is good")

    judgement = present(_JUDGEMENT)
    if judgement:
        score += 2
        signals.append(f"the task turns on judgement, not just correctness "
                       f"({', '.join(judgement[:3])})")

    mechanical = present(_MECHANICAL)
    if mechanical and not judgement:
        score -= 1
        signals.append(f"the work looks mechanical ({', '.join(mechanical[:3])})")

    consequence = present(_CONSEQUENCE)
    if consequence:
        score += 1
        signals.append(f"failure here is expensive or hard to reverse "
                       f"({', '.join(consequence[:3])})")

    if words > 120:
        score += 1
        signals.append(f"the task is long ({words} words), so more of it can be "
                       f"missed without any check noticing")

    if score >= 2:
        strategy = "reviewed"
    elif score <= -1:
        strategy = "solo"
    else:
        strategy = "reviewed"
        signals.append("the signals do not agree; review is the cheaper mistake")

    # Consequence is a floor, never a ceiling.
    if (consequence or risk in ("high", "critical")) and strategy == "solo":
        strategy = "reviewed"
        signals.append("raised to `reviewed`: consequence sets a floor regardless "
                       "of the other signals")

    # Council is never proposed automatically. It has NEVER been run, and the only
    # external evidence on panels is 17.2x error amplification at roughly 7x the
    # tokens. Proposing an unmeasured, expensive mechanism by default is exactly
    # the pattern that produced this programme's three nulls.
    return {
        "schema_version": 1,
        "proposed": strategy,
        "signals": signals,
        "score": score,
        "confidence": "low",
        "basis": ("measured and humbled: on the one family benchmarked (family J, "
                  "3 trials per arm), this proposal picked `reviewed` and that arm "
                  "won ZERO of the measured axes. The proposal stays low-confidence "
                  "for a measured reason now. Override it freely; the record exists "
                  "so choices keep getting correlated with outcomes."),
        "council_note": ("`council` and `full` are never proposed automatically: the "
                         "support stack has never been run (dg-d was designed and never "
                         "executed), and the external evidence on panels is 17.2x error "
                         "amplification at ~7x the tokens. Ask explicitly with "
                         "--strategy council or --strategy full."),
        "reason": _reason_from(strategy, signals),
    }


def _reason_from(strategy: str, signals: list[str]) -> str:
    """A reason long enough to survive the declaration gate, built from the signals."""
    if not signals:
        return (f"chose {strategy} because no signal in this task argued for anything "
                f"stronger than the default path")
    return f"chose {strategy} because " + "; and ".join(signals[:3])


def describe() -> str:
    lines = ["EXECUTION STRATEGIES — declare one at task start", ""]
    for name, s in sorted(STRATEGIES.items(), key=lambda kv: kv[1]["rank"]):
        lines.append(f"  {name}")
        lines.append(f"      {s['purpose']}")
        lines.append(f"      choose when:")
        for row in s["choose_when"]:
            lines.append(f"        - {row}")
        lines.append(f"      measured: {s['measured']}")
        lines.append("")
    lines.append("A declaration needs a REASON in your own words that refers to THIS")
    lines.append("task. 'it seemed appropriate' is not a reason and is rejected.")
    return "\n".join(lines)


def resolve(strategy: str, risk: str = "medium", provider: str = "anthropic-claude-code",
            executor_profile: str | None = None) -> dict:
    """Turn a strategy's profiles into concrete model selectors.

    `executor_profile` overrides the preset's base tier, because the owner's
    model is COMPOSITION: the support stack (reviewer, council) and the executor
    tier are orthogonal knobs. "opus solo" is `solo` with a strong executor;
    "cheap everything" is `full` as shipped. Without this override the ladder
    quietly hard-wired one base per rung and "just run it on opus, no support"
    was impossible to declare at all.
    """
    if strategy not in STRATEGIES:
        raise ValueError(f"unknown strategy {strategy!r}; expected one of {sorted(STRATEGIES)}")
    sys.path.insert(0, str(HERE))
    import resolve_capability_profile as rcp

    spec = dict(STRATEGIES[strategy])
    if executor_profile:
        spec["executor_profile"] = executor_profile
    out: dict = {"strategy": strategy, "provider": provider, "roles": {}, "automation_allowed": True}

    def one(role: str, profile: str | None) -> None:
        if not profile:
            out["roles"][role] = None
            return
        try:
            decision = rcp.resolve(provider, profile, risk)
            out["roles"][role] = {"profile": profile, "selector": decision["selector"],
                                  "effort": decision["effort"]}
            if decision["catalog_expired"]:
                out["automation_allowed"] = False
        except (ValueError, FileNotFoundError, KeyError) as error:
            out["roles"][role] = {"profile": profile, "selector": None,
                                  "unresolved": f"{type(error).__name__}: {error}"}
            out["automation_allowed"] = False

    one("executor", spec["executor_profile"])
    one("reviewer", spec["reviewer_profile"])
    out["council"] = []
    for index, profile in enumerate(spec["council_profiles"]):
        one(f"council_{index}", profile)
        out["council"].append(out["roles"].pop(f"council_{index}"))
    return out


def declare(strategy: str, reason: str, risk: str = "medium",
            executor_profile: str | None = None) -> dict:
    """Validate and build the declaration that gets written into the pack."""
    if strategy not in STRATEGIES:
        raise ValueError(f"unknown strategy {strategy!r}; expected one of {sorted(STRATEGIES)}")
    words = [w for w in reason.split() if w.strip()]
    if len(words) < REQUIRED_REASON_WORDS:
        raise ValueError(
            f"the reason is {len(words)} words; at least {REQUIRED_REASON_WORDS} are required. "
            f"Say what about THIS task made you choose {strategy!r}. A choice nobody can "
            f"argue with later is a choice nobody can learn from.")
    resolved = resolve(strategy, risk, executor_profile=executor_profile)
    return {
        "schema_version": 1,
        "provenance": "authored",
        "strategy": strategy,
        "reason": reason.strip(),
        "risk": risk,
        "models": resolved,
        "note": ("The agent chose this. That is provenance `authored`, which this "
                 "programme has measured at zero for correctness three times. It is "
                 "recorded so the choice can be correlated with the outcome later, "
                 "not because choosing is itself worth anything."),
    }


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--declare", choices=sorted(STRATEGIES))
    parser.add_argument("--reason", default="")
    parser.add_argument("--risk", default="medium", choices=["low", "medium", "high", "critical"])
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    if args.list or not args.declare:
        print(describe())
        raise SystemExit(0)

    record = declare(args.declare, args.reason, args.risk)
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "execution-strategy.json").write_text(
            json.dumps(record, indent=2) + "\n", encoding="utf-8")
    roles = record["models"]["roles"]
    print(f"strategy: {record['strategy']}")
    print(f"  executor: {(roles.get('executor') or {}).get('selector')}")
    print(f"  reviewer: {(roles.get('reviewer') or {}).get('selector') or '-'}")
    if record["models"]["council"]:
        print(f"  council : {[c.get('selector') for c in record['models']['council']]}")
    print(f"  automation_allowed: {record['models']['automation_allowed']}")


if __name__ == "__main__":
    main()
