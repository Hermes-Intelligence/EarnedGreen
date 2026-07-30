# Earned Green

**Stop your agent reporting "done" when it isn't.**

```bash
git clone <this repo> && cd earned-green
python -m awbp demo
```

No install, no API key, no network, no config. It runs in under a second and
prints this:

```text
── ARM 1   the suite the change writes for itself ─────────────────────────
          provenance: authored (rank 1 of 4) — measured at zero lift, 9 runs

     PASS  trims surrounding whitespace from string fields
     PASS  lowercases the email field
     PASS  drops rows with no id
     PASS  coerces a numeric amount string to int
     PASS  leaves unknown fields untouched
     PASS  collapses a duplicate id to a single row
     PASS  strict mode raises when a row carries no id

    7 of 7 checks pass.  VERDICT: done.

── ARM 2   predicates derived from this module's own repair history ───────
          provenance: diff-derived (rank 4 of 4)

    calibration: all 2 hold on the code that was there before the change.
    So a red below is about the change, not about the predicate.

     FAIL  the returned rows must match the repaired behaviour
           derived from a1b2c3d  fix: keep the LAST row for a duplicate id
     FAIL  the caller's list must be left exactly as it was passed
           derived from e4f5a6b  fix: stop normalising the caller's rows in place

  NOT MECHANICALLY COVERED BY ARM 1 — 2 behaviour(s) broken

    silent_defect_rate    arm 1: 0.22      arm 2: 0.00
```

Same change. Same repository. Two verdicts. **The disagreement is the product.**

The model's diff is frozen so the demo needs no provider. Everything else runs
when you run it, including the derivation of those two predicates, which nobody
wrote: they are the observed difference two real repairs made, replayed live.

---

## The number

On a real production campaign, the unassisted arm reported the task complete on
**every trial** with **2 of 8 required behaviours broken**.

| | reported "done" with broken behaviours |
|---|---:|
| well-configured agent, no harness | **25%** |
| same agent, same model, this harness | **0%** |

Two further families, measured with predicates mined from each repository's own
repair history: **88.7 against 33.3**, and **71.3 against 43.0**. The baseline in
both was well-configured, not a straw man.

Three other ideas in this repository measured **exactly zero** and are documented
at the same length as the wins. [`BENCHMARKS.md`](BENCHMARKS.md) has all of it,
including the retraction.

---

## What it actually is

Not a prompt library and not an agent framework. It is a **measuring instrument
for agent work**, and its one job is to make an unearned green impossible to
report.

Every mechanism that survived measurement here does the same thing: it changes
**what gets reported and when the harness refuses to grade**. Every mechanism
that tried to change what the model *does* measured zero. That is the finding the
whole repository is organised around.

### The four questions it asks before work starts

**1. Where will the oracle come from?** Asked before anything else, because it
decides what a green is worth.

```bash
python awbp/oracle_plan.py --repo /path/to/your/repo
```

Ten seconds, zero config, on any repository. It reports the strongest oracle
*your* repo can actually supply, ranked by the measured ladder — and says
`WEAK` to your face when the only thing available is the task description.

**2. Who does the work and who checks it?** Declared at task start with a reason
of at least eight words that refers to *this* task. `solo`, `reviewed` (cheap
executor plus strong adversarial reviewer), or `council`. Each carries its own
measurement history rather than a recommendation, because on the one campaign
that compared them the cheap-plus-reviewer arm produced the best-formatted
document at **52% of the cost** and dropped three of four checkable figures.
There is no winner, so there is no default.

**3. Where does user-visible state live in production?** One field. It exists
because a spec line saying "local-first is fine" produced a polished team board
that stored the whole team's data in one person's browser, and nobody noticed
until someone asked whether it worked in production.

**4. Can the instrument tell good from hollow?** If it cannot, the harness
**refuses to grade**. Not a weaker verdict — no verdict. A result from an
uncalibrated instrument is not a weak result, it is not a result.

### Use it on your own repository

```bash
python -m awbp init                       # detect the stack; verify the tests run today
python -m awbp task "what you want done"  # route it, freeze the baseline and the suite
python -m awbp check                      # run the frozen suite
python -m awbp probe                      # revert each hunk: does anything notice?
```

Nothing is installed, no PATH is touched, and nothing is written into your
repository except `.agentic/`.

### Or use it without cloning it

The read-only half speaks MCP over stdio, standard library only, no dependencies:

```json
{
  "mcpServers": {
    "earned-green": {
      "command": "python",
      "args": ["-m", "awbp", "mcp"],
      "cwd": "/path/to/earned-green"
    }
  }
}
```

Five tools: `oracle_plan`, `host_rules`, `check_calibration`, `coverage_manifest`
and `demo`. Every one of them reads. The commands that write stay in the CLI on
purpose, so an agent reaching through a socket cannot snapshot your workspace as
a side effect of asking a question — and the test suite asserts that by
fingerprinting a repository before and after every tool runs against it.

---

## Why the honesty is the point

The single most repeatable finding across this whole programme is uncomfortable:

> **The instrument is wrong more often than the work is.**

One day's session produced eighteen defects in instruments and none in the work
they were grading. The dangerous ones all produced *plausible numbers* — a
predicate whose word boundaries had been written into the source as literal
backspace bytes, so it matched nothing, reported PASS for its whole life, and
made every document it touched look checked.

That is why nothing here ships unmeasured, why the nulls stay in the README, and
why the calibration gate exists at all.

---

## Layout

| path | what is in it |
|---|---|
| [`awbp/`](awbp/) | the tool. Every module runs standalone; `python -m awbp` dispatches |
| [`awbp/demo/`](awbp/demo/) | the fixture above. 30 lines before, 30 lines after — read them |
| [`BENCHMARKS.md`](BENCHMARKS.md) | every campaign, every null, every retraction |
| [`START-HERE.md`](START-HERE.md) | written for the agent, not for you |
| [`Runtime/stable/manifest.json`](Runtime/stable/manifest.json) | what is promoted, and what each release refused to claim |
| [`Evals/`](Evals/) | fixtures, run records, and the harness that produced the numbers |
| [`Research/`](Research/) | candidate packages. Never authoritative; promotion is a separate act |

Just cloned this and want the agent to drive? Say one thing:

> **"Read `START-HERE.md` and use it."**

---

## Status

Release **0.6.5**. Measured on six task families across four production
repositories. Positive on two, null on three, saturated on one.

The cost router is wired and **unmeasured at n=1**. The execution-strategy
declaration is recorded and **has no outcome correlation yet**. Both say so in
their own output.
