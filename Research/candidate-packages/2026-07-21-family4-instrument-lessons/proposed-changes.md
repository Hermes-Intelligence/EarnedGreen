# Candidate: instrument changes earned by family-4 (Idea Tracker)

**Status:** candidate. Nothing here has been promoted to Stable.
**Evidence:** `workstreams/idea-tracker/LESSONS-for-the-environment.md` (full trace,
with the campaign receipts) — this file is the change list only.
**Provenance:** measured during the family-4 campaign (first from-scratch regime)
and the production-backend build that followed it, 2026-07-20/21.

---

## Why this candidate exists

Family-4 was the first campaign in the **from-scratch** regime: no history, no
baseline containing the surface, oracle bootstrapped from the spec. Two things
happened that the current instrument is not built for:

1. The mechanical half **saturated** (100% vs 91%) while the human half
   discriminated cleanly — and every owner note landed in the gap between
   "the feature exists" and "the feature is usable and belongs in this codebase".
2. Three separate times, a **wrong score came from the harness**, not the work.
   Two of the three produced plausible numbers.

The changes below address those two facts. All are buildable with zero provider
calls.

---

## C1 — Calibration as a precondition of grading  *(highest value)*

**Now.** Calibration (known-good high, known-hollow low) is run once when an
instrument is built, then trusted.

**Proposed.** `grade_arm` refuses to grade until it has re-graded both fixtures in
the same invocation and both land in their registered bands. A harness that
cannot distinguish good from hollow reports itself broken instead of reporting a
number.

**Earned by.** Three harness defects in this campaign: playwright's
last-registered-first route resolution shadowing the API stubs (this alone was
the 65% → 86% swing); an unset `VITE_API_BASE_URL` that would have scored every
arm a believable zero; and a shell that rewrote `/api` into a Windows path in the
build environment. C1 catches all three on the first run.

**Cost.** Seconds per grading run. No new concepts.

---

## C2 — `red-on-hollow` admission for from-scratch tasks

**Now.** A predicate is admitted if it is RED on the baseline (the vacuity gate).

**Problem.** In the from-scratch regime the baseline is *absence*, so the most
valuable predicates are trivially green and the gate — correctly, by its own
rule — rejects them. This is not hypothetical: `phone-no-overflow` was written,
was rejected as vacuous, went to `named-unverified`, and the board shipped with
the overflow bug the owner then found by eye.

**Proposed.** When the task's baseline does not contain the surface at all, admit
on RED-against-the-hollow-fixture instead. The hollow fixture *is* the
from-scratch baseline — we already build one for calibration.

**Interaction with C1.** C1 makes the hollow fixture load-bearing at grade time,
so C2 costs nothing extra to run.

---

## C3 — `layout-invariants` predicate kind

**Proposed.** A predicate kind evaluated at 2–3 viewport widths in the pass we
already run:

- the page's own `scrollWidth` never exceeds its `clientWidth` (only a named,
  intentionally-scrolling container may),
- computed font-size of primary text ≥ a floor read from the host's tokens,
- foreground/background pairs resolve to tokens present in the host palette.

**Earned by.** Four of the owner's first five notes: board cut off after the last
column, fonts too small, counter unreadable, eyebrow the wrong colour. All four
were invisible to sixteen static and seven runtime presence predicates.

**Depends on C2** — these are exactly the predicates the vacuity gate rejects in
this regime.

---

## C4 — `state_lives_in` on the task record

**Proposed.** One required field for any task creating or mutating user-facing
state: where does the state live in production, and who else can see it?
`browser-only (demo)` is a permitted answer — it just has to be *chosen*.

**Earned by.** The spec said "local-first is fine and expected; no backend is
being built here". The agents obeyed it exactly and produced a polished *team*
board storing the team's ideas in one person's browser. Nobody noticed until the
owner asked. The scope line was correct; nothing connected it to shippability.

---

## C5 — At least one interaction predicate per feature dimension

**Proposed.** A dimension covered only by presence predicates is treated as
`named-unverified`, the same as a dimension with no predicate. Coverage requires
at least one scripted `act → reload → assert`.

**Earned by.** Making `create()` asynchronous (part of the backend wiring) broke
"a new card opens for typing": the card still mounted, still existed, and every
presence predicate stayed green. Only click-type-reload found it. The same shape
of check is what proved the backend wiring afterwards — nine assertions, each a
round trip through a reload.

---

## C6 — Host-conformance section derived from the codebase

**Proposed.** The spec-first bootstrap emits a conformance section extracted
**mechanically from the host repo**, not from the task prose: the tokens, sizing
tables and idioms the sibling surfaces already use, turned into predicates.

**Earned by.** Two owner notes — the eyebrow accent colour and the nav icon size —
were not taste at all. The correct answer was sitting in the repo, in the sibling
internal surfaces, in a config table. `nav-icon-size-matches-siblings` is a
one-line assertion against data that already exists. This is the
"repo-as-immune-system" claim at its most literal, and the environment pointed
neither arm at it.

---

## C7 — Rule: a stand-in must be faithful in the boring ways

**Proposed.** Add to the harness-authoring rules: a fake that returns live
references, or that lets framework-injected defaults arrive unresolved, **invents
failures**. Copy rows on the way out; pass injected parameters explicitly. When a
fake does produce a false failure, check whether it points at real fragility
before dismissing it.

**Earned by.** The in-memory database written for the backend test produced two
false failures — live row aliasing (a route read its own pre-update snapshot
through the update it had just issued) and an unresolved FastAPI `Query(False)`
default. Neither was a product bug. The first nonetheless pointed at genuine
fragility, which was then hardened.

---

## Priority

1. **C1** — cheapest, catches the failure mode that has cost the most.
2. **C2** — unlocks the whole predicate class the regime currently cannot admit.
3. **C3** — four of the owner's first five notes.
4. **C4** — one field; prevents an unshippable "finished" feature.
5. **C5**, **C6**, **C7**.

---

# Direction: what the whole programme now says the environment is for

C1–C7 are instrument repairs. This section is the larger claim they add up to,
read across every campaign we have run — not only family-4.

## The pattern in the measurements

| What was measured | Result |
|---|---|
| Adaptive mode ladders / scaffolding | decisive **null** (5 fixtures, 10 calls) |
| Agent-authored, gate-admitted checks | **zero** lift over well-configured vanilla (9 runs, all 92) |
| Notes-as-code (routed executable lessons) | transfers style, **not predicate strength** |
| Diff-derived predicates + forcing loop | **positive on two measured-hard families** (88.7 vs 33.3; 71.3 vs 43.0) |
| `silent_defect_rate` | loop **0.0** vs bare vanilla **0.25** |

Read together: **everything the agent authors about its own correctness buys
nothing. Everything that comes from outside the agent, and is then made
impossible to declare away, buys a lot.**

That is the whole thesis, and it has now failed three times in the same direction
and succeeded twice in the same direction.

## Four consequences

**D1 — Rank oracle sources by distance from the agent, and route on it.**
Measured strength, strongest first: diff-derived (from real commits) → host-codebase
derived (tokens, sizing, sibling idioms — mechanically extractable) → spec-derived
(saturates) → agent-authored (measured zero). Provenance is already recorded; it
is not yet used to *prefer* or to *route*. It should be.

**D2 — Report oracle independence as a number.** Per task: what share of admitted
predicates came from a source the agent did not author. Family-4 would have
scored ~0% — every predicate was spec-derived. That number, shown at task start,
is a better predictor of whether the green means anything than any verdict.

**D3 — The most valuable output is the list of what is NOT covered.** The
machinery for this already exists (`named-unverified`), and family-4 proves it
works: the overflow predicate was correctly rejected as vacuous, the dimension
was correctly marked unverified — and nobody read it, because the summary led
with the green. Invert the presentation: a task report opens with *"N behaviours
you asked for are not mechanically covered"*, by name. The owner would then have
been looking at the overflow dimension before he ever opened the build.

**D4 — Shrink where the measurements are null.** Mode ladders, authored-check
ceremonies and notes-as-code have each been measured at zero. Mechanisms that
have not earned a measurement should carry a sunset date rather than accumulate.

## A standing practice, not a mechanism

After every human review, **classify the notes** and ask of each class: could this
have been mechanical? Family-4's nine owner notes split into fit/legibility (3),
host-conformance (2), taste (1), undeclared capability (3) — and six of the nine
were mechanically checkable with predicates we did not have. Repeating that
classification after each campaign turns real use, rather than my imagination,
into the instrument's roadmap.

---

## Limits of the evidence

n = 1 per arm on family-4. The owner's blind pick agreeing with the mechanical
ranking is suggestive, not a verdict — Board A won on two sub-points, and the
mechanical gap traced to a single defect. **The instrument findings (C1–C7) are
held with much more confidence than any claim about the arms**, because each one
is a thing that demonstrably went wrong, repeatedly, with receipts.
