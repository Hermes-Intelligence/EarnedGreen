# Earned green: checks that must prove they discriminate

*Release 0.5.0. See also [adaptive-modes.md](adaptive-modes.md) for the loop this extends, and
[benchmarking/verification-loop-results.md](benchmarking/verification-loop-results.md) for the
measurement that justified it.*

## The problem 0.4.0 left open

Release 0.4.0 shipped a measured result: an independently executed verification loop takes a
frontier agent from 77 to 100 on a real proprietary task. But **the loop is worth exactly the
quality of its checks**, and in 0.4.0 those checks were hand-written per fixture. Fine for a
benchmark. Useless on a Tuesday.

That left three gaps with one root — *we never validated the checks themselves, only the work
against them*:

| Gap | 0.4.0 | Consequence |
|---|---|---|
| Who authors checks? | A human, per fixture | A fresh repo got the guardrail half (symbol sweep, existing tests, a gate that refuses lies) and never the quality half. |
| Clone-and-use | `compile_check_suite` hardcoded `tests/` and `python3 -m unittest` | "Simple" only for the shape the harness was built against. |
| Confidence | A green suite means "the checks passed" | [SpecBench](https://arxiv.org/abs/2605.21384): a saturated visible suite is where hacking hides, not where it is absent. |

## The mechanism

A green result is **earned** only if all three hold. Anything else is **claimed** green, and the
harness refuses to certify it.

### 1. Vacuity gate — zero model calls

Every proposed check runs against the **pre-change baseline snapshot** the harness already takes:

| `expectation` | required baseline result | otherwise |
|---|---|---|
| `red-before-green-after` | **FAIL** | vacuous → rejected |
| `green-before-green-after` | **PASS** | asserts something already broken → rejected |

A check that passes before the feature exists proves nothing about the feature.

**The subtlety that makes it real:** the baseline failure must be an **assertion**, not an
import/collection error. `import new_module` → `ImportError` → red; the agent then creates an
empty module → green. Vacuous, and it sails through a naive gate. So an error-red is
`suspicious-red`: not admitted on its own. Authors are briefed to import *inside* the test and
assert on behaviour, so the assertion is what fails.

### 2. Necessity probe — zero model calls

After green, the harness reverts each substantive hunk of the change and demands that some
**behavioural** check goes red. An uncovered hunk is either **unnecessary code** or **untested
code**; both are worth surfacing, and a green suite next to code no check can reach is exactly
what "looks done, isn't" is made of.

Hunk-revert rather than classic mutation testing (PIT/Stryker/mutmut) is deliberate: it operates
on the diff, not on an AST, so it is language-agnostic, dependency-free, deterministic, and its
message is directly actionable — *"reverting src/api.py:40-48 breaks no check"*.

### 3. Adversarial review — and the part that needed solving

Brief a hostile subagent: *pass every frozen check with an implementation that does the wrong
thing.*

The obvious version of this does not work. **"Wrong" needs somebody who knows it is wrong.** A
benchmark has a held-out oracle; a user's repo on a Tuesday has nothing — so an adversary "win"
would be the adversary's own unverifiable claim, and we would have replaced a check we cannot
trust with an opinion we cannot trust either.

So the adversary must also supply a **divergence witness**: a deterministic program that observes
behaviour. The harness then establishes, with no oracle and no judgement:

> the frozen suite is **green** on the attack, **and** the witness **observably diverges** between
> the attack and the real implementation

Then the suite provably cannot distinguish two programs that behave differently, and at most one
of them satisfies the requirement. That is a demonstrated hole, not an accusation. **Which one is
correct is deliberately not decided** — that needs the requirement, and that is what goes to a
human.

Verdicts: `checks-held` · `suite-defeated` · `no-divergence` (green attack, nothing observable
separates it) · `inconclusive` (nondeterministic witness, broken witness, unusable response). An
attack that could not be run is never reported as an attack the checks defeated.

## Using it

Two commands, from the repository you are in. Nothing is installed; nothing is written into the
repo except `.agentic/`; no step makes a network call.

```
python tools/adaptive/awbp.py init                  # once per repo: detect the stack, verify tests are green today
python tools/adaptive/awbp.py task "<what you want>"   # route, snapshot the baseline, freeze the suite
python tools/adaptive/awbp.py author                # write the check brief for a clean-context subagent
python tools/adaptive/awbp.py admit <reply-file>    # only discriminating checks are frozen in
python tools/adaptive/awbp.py check                 # run the frozen suite (what the loop and the gate run)
python tools/adaptive/awbp.py probe                 # is the green EARNED?
python tools/adaptive/awbp.py adversary [reply]     # brief, then judge, an attack on the checks
```

For an agent, [`START-HERE.md`](../START-HERE.md) at the repository root is the whole onboarding:
point Claude or Codex at that one file.

**No provider integration is required.** `awbp` never calls a model. It emits briefs and judges
responses; the agent driving the session spawns the author and adversary subagents itself. Spend
stays where the approval ceiling lives.

## Evidence

**Retroactive, on release 0.4.0's own winning trials:** the 100/100/100 was **earned** —
`necessity_ratio = 1.0` on all three `standard-loop` trials, zero uncovered hunks. That is the
first independent answer to the objection that a saturated visible suite is theatre. Cost: zero
calls. (`evidence/necessity-retro-standard-loop.json`.)

**End-to-end, on a repo the environment had never seen** (2026-07-16, real subagents, zero
benchmark calls): a clean-context author's check was admitted 1/1 — it used `getattr` + `assert`,
so the baseline red was an assertion, exactly as briefed. The implementation went GREEN and the
probe said EARNED. A real adversary then **defeated that suite**: it hard-coded the three asserted
pairs and fell through to `total - pct` with no bounds check. The frozen suite is green on both;
the witness diverges —

```
real implementation   discount(100,200) = ValueError    discount(50,25) = 37.5
attack                discount(100,200) = -100          discount(50,25) = 25
```

No oracle was consulted. The suite provably could not tell right from wrong there.

## What this does not do, stated plainly

- **The vacuity gate proves a check DISCRIMINATES, not that it is CORRECT.** A wrong-but-
  discriminating check passes both nets. `requirement_ref` makes that a seconds-long human check;
  it does not make it impossible.
- **Pure refactors have no "red before".** The gate degrades to differential + necessity probe
  there. That is by design, not a surprise to discover mid-task.
- **The adversary bounds the suite, it does not certify it.** `checks-held` means *this attack*
  failed. Read which check caught it: an attack that died on something unrelated to the task
  failed by accident and proves little — which is why the harness always names the catching
  checks.
- **We cannot fix the miss rate of agent-authored checks.** [PBT-Bench](https://arxiv.org/abs/2605.15229)
  measures agent-derived properties missing 17–58% of seeded bugs. The contribution here is not a
  better author; it is refusing to certify when the suite's discriminating power is weak.
- **The freeze is per-task**, which bounds rather than refutes
  [The Verification Horizon](https://arxiv.org/abs/2606.26300)'s point that fixed verifiers decay
  as capability grows.

## Prior art, honestly

The parts are old: TDD's red-green, mutation testing, property testing, adversarial review. The
2026-07-16 research pass found **no source** describing an agent loop where the agent authors the
checks → the harness admits them only if they demonstrably discriminate → freezes them → and then
refuses "done" until every hunk survives a necessity probe. Adjacent and cited above:
PBT-Bench, SpecBench, [CapCode](https://arxiv.org/abs/2606.07379), The Verification Horizon.

The metric worth publishing, and not yet measured: **`silent_defect_rate`** — the share of defects
a held-out oracle catches that the visible suite missed. It states plainly how often the
environment would have said "done" when it was not.
