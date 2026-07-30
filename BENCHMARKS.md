# Earned Green — benchmarks

Every campaign this repository has run, including the ones that measured nothing.

Three of the ideas here were popular, plausible, and worth building. All three
measured **zero**. They are listed at the same size as the wins, because a
repository that only publishes its wins is not measuring, it is advertising.

---

## How to read this

**Pre-registration.** Predictions and arm definitions were written to a file
*before* any spend, and every campaign below links the file. Where a prediction
failed, the failure is recorded next to the prediction rather than removed.

**Provenance.** Every result carries the rank of the oracle that produced it. The
ranking is measured, not assumed:

| rank | source | what it means |
|---:|---|---|
| 4 | `diff-derived`, `data`, `repo-tests` | predicates from a real prior repair, a live datastore, or a suite written before the task existed |
| 3 | `host`, `relation`, `acceptance` | rules extracted mechanically from the codebase being worked in |
| 2 | `spec` | the task description turned into predicates |
| 1 | `authored`, `council` | the agent's own checks, or a panel of models |
| 0 | `reviewed-unverified` | a model said it looked right |

The independence floor sits at 3, deliberately **above** `spec`.

**Two axes, not one.** `score` is how much of the asked-for work is correct.
`silent_defect_rate` is the share of required behaviours that are broken *at the
moment the agent reports done*. The second is the one this project is about, and
it is the one that saturates last.

> **What the dollar figures are.** These runs execute the **Claude Code CLI inside a
> dedicated WSL distro on a subscription**, not metered API calls. The adapter's own
> default cost basis is the string `not-reported-by-subscription-cli`, and every run
> record carries `"provider-reported-usd; subscription charge may differ"`. The
> amounts below are the CLI's **token-value estimate**, useful for comparing arms
> against each other and useless as an invoice. The real budget is subscription
> quota and wall-clock time.

**Task families are described, not named.** The work ran on private production
repositories. Enough detail is given to judge the difficulty; nothing identifies
the systems.

---

## Results

| # | task family | regime | oracle rank | arms × trials | headline |
|---|---|---|---:|---|---|
| 1 | legacy document-parser rework, Python ingest service | repair | 4 | 4 × 3 | **first envelope measurement**: `silent_defect_rate` 0.00 vs 0.25 |
| 2 | era/versioning migration, JS web app | repair | 4 | 2 × 3 | **88.7 vs 33.3** |
| 3 | analytics feature on an existing surface, JS web app | extend | 4 | 2 × 3 | **71.3 vs 43.0** |
| 4 | citation rendering in a report builder, JS | extend | 4 | 3 × 3 | **NULL** — all 9 runs scored 92 |
| 5 | internal board app, built from nothing | from scratch | 2 | 2 × 1 | **saturated** — instrument could not separate |
| 6 | client-facing document, built from nothing | from scratch | 4 | 3 × 1 | brand conformance only; claims axis tied |
| 7 | design system + data-bound spec, judgement regime | from scratch | 4 (bindings) / 1 (beauty) | 4 × 3 + canary | **the proposed strategy won nothing**; honesty-depth trade lives between models, not strategies |

---

## The wins

### Family 2 — era/versioning migration (JS)

An agent must carry a change across a versioned boundary where the old and new
shapes coexist. The instrument was built from **nine real prior repairs** mined
out of the repository's own history: each repair replayed, the observed
before/after difference frozen as a predicate, each predicate required to go red
on the code its repair replaced.

| arm | per-trial | mean |
|---|---|---:|
| well-configured baseline | 50 / 33 / 17 | **33.3** |
| oracle loop | 100 / 83 / 83 | **88.7** |

Note the baseline is **well-configured**, not bare. It had the same model, the
same repository, the same task text and a competent prompt. The gap is not
prompt quality.

**What this does not show.** Both arms scored `silent_defect_rate` 0.00 here.
The envelope advantage measured in family 1 did **not** replicate on this family,
and the pre-registered prediction P-D4 was falsified in exactly the half it was
written for. It is recorded as falsified.

### Family 3 — analytics feature on an existing surface (JS)

Same recipe on a different family, run to test whether family 2 was a fluke.

| arm | per-trial | mean |
|---|---|---:|
| well-configured baseline | 29 / 71 / 29 | **43.0** |
| oracle loop | 71 / 86 / 57 | **71.3** |

The sharpest regularity across both: the loop's **floor** sits at roughly the
level a bare canary reaches, while unforced arms fall below it. The loop is not
raising a ceiling; it is refusing to let the work stop early.

### Family 1 — the envelope measurement

The one campaign where `silent_defect_rate` separated the arms.

| arm | `silent_defect_rate` at "done" |
|---|---:|
| bare baseline | **0.25** |
| oracle loop | **0.00** |

The baseline reported the task complete on every trial with **2 of 8 required
behaviours broken**. Neither broken behaviour was visible in the diff.

**Caveat, unrepaired and stated in full.** The fixture's sample builder leaks the
shape of the intended fix. The 100/100/100 headline from this family's score axis
is therefore **not** published as clean, and the correctness-lift framing derived
from it was **retracted** in release 0.6.0 after the null replicated on two
further families. What survives from this campaign is the envelope number above,
which does not depend on the leak.

---

## The nulls

These are the results the project is most confident about, because each one
contradicts something we had already built.

### Null 1 — self-authored checks buy nothing

**The idea.** Have the agent write its own checks in a clean context, then admit
only the ones that provably fail on the pre-change code. Ceremony that survives
an admission gate should be worth something.

**The measurement.** Family 4. Three arms — bare, well-configured, full loop with
authored-and-admitted checks — three trials each.

**The result.** All nine runs scored **exactly 92**. All nine failed **exactly
the same dimension**. `silent_defect_rate` was **0.125 for every arm**. There is
no separation of any kind to interpret.

**The diagnosed cause, which is the useful part.** The loop machinery worked: it
caught real failures and forced fixes on the dimensions it covered. But on the
hardest dimension, the clean-context author wrote a check grounded in a *weaker
observable than the oracle's* — layout geometry where the oracle read emitted
text. The suite went green on iteration one, so no iteration budget could ever
have forced the fix: **more loops cannot find a defect the suite cannot see.**

Self-authored checks have a measured ceiling, and it is set by the author's
imagination, not by the loop.

### Null 2 — the mode ladder

**The idea.** Route each task to a tier of ceremony proportional to its risk:
light for reversible work, heavy for irreversible.

**The result.** Zero correctness lift across every family it was measured on. The
ladder is retained only as a scoping guardrail. It is not a correctness mechanism
and the manifest says so.

### Null 3 — notes as code

**The idea.** Carry executable lessons forward between tasks so the agent stops
repeating known mistakes.

**The result.** Measured transfer of **style but not predicate strength**. The
author read the note, applied its form, and still wrote a predicate weaker than
the rule the note encoded. The mechanism was retired by its own
earned-persistence rule.

**What the three nulls have in common.** Every one of them tried to change what
the model *does*. Every mechanism that has survived measurement instead changes
**what gets reported and when we refuse to grade**.

---

## From-scratch regime

When there is no prior version, there is no diff to derive from, and the whole
recipe above loses its footing.

### Family 5 — internal board app

Two arms, spec-derived instrument (rank 2). Both builds scored near-identically.
Minutes later a human found **four defects by eye** that the instrument had not
seen. This is what rank-2 saturation looks like, and it is why `spec` sits below
the independence floor.

The response was not a better spec instrument. It was `red-on-hollow`: in the
from-scratch regime a deliberately hollow fixture replaces the absent baseline as
the admission surface.

### Family 6 — client-facing document, three arms

| | A: baseline | B: environment | C: environment, cheaper base |
|---|---|---|---|
| model | frontier | frontier | mid-tier |
| wall clock | 21.9 min | 22.7 min | **17.9 min** |
| output tokens | 81,615 | 72,092 | **54,608** |
| cost | $11.07 | $10.18 | **$5.79** |
| house-style violations | 0 | 0 | 0 |
| claims axis *(hidden from all arms)* | all pass | all pass | all pass |
| brand conformance | wrong palette, tagline missing | **correct** | **correct** |

**What it shows.** Exactly one thing, and it is the smallest of the three that
looked promising: **brand conformance**. Arm A had the brand book in the
repository and did not mine it. Arms B and C were handed rules extracted
mechanically from that same file and used them. The answer was in the repo; the
arm that got it mechanically used it. That is rank-3 `host` provenance earning
its place.

**What it does not show.**

- *B's craft pass is partly tautological.* B held the craft checker and was told
  to iterate against it. Passing it is the mechanism working, not independent
  evidence of better craft. It is not counted as a win.
- *The claims axis tied.* Pre-registered prediction P-2 said the environment
  would win there by ≥15 points. It did not. The task saturates on claims, as
  the difficulty canary had already warned.
- *The house-style instruction needed no loop.* Zero violations in every arm,
  down from 52 in the canary. Telling the model was sufficient.
- *Cost is n=1.* Arm C delivered the best-formatted document at **52% of arm A's
  cost** and lost three of four checkable figures. One task, one trial per arm.
  That is a reason to build the cost router, not a reason to trust it.

### Family 7 — the execution-strategy benchmark (first half)

The first controlled comparison of working methods rather than harnesses: the
same judgement-heavy design task (a visualization vocabulary plus a
machine-checkable data-binding spec) run as four arms, three trials each, on a
ladder sharing one cheap base — solo-frontier, solo-cheap, cheap+reviewer,
cheap+reviewer+council. Support roles ran as in-session subagents; the council's
first flight ever is confirmed in provider telemetry (three models in one run).

| arm | real bindings (mean) | invented (silent) | style violations | relative cost |
|---|---:|---:|---:|---:|
| frontier solo | **18.7** | 4.3 (2.3) | **14** | 1.0x |
| cheap solo | 9.3 | **0.0 (0.0)** | 84 | 1.0x |
| cheap + reviewer | 6.0 | 6.3 (3.3) | 71 | 2.8x |
| cheap + reviewer + council | 13.7 | 2.0 (0.7) | 74 | 3.5x |

Four of five pre-registered predictions were graded; **three were falsified**,
one confirmed for the wrong mechanism, and the one that mattered most —
"the environment's automatic strategy proposal picks the winning arm" — was
falsified outright: the proposal picked the reviewer arm, which won nothing and
contained the campaign's single worst artifact (zero real bindings, seventeen
invented endpoints, nine of them absent from its own gap report).

**The finding worth the quota: the honesty-depth trade lives between MODELS,
not between strategies.** The frontier model wires twice as many real endpoints
and writes cleaner prose, but fabricates a handful, mostly silently. The cheap
model never fabricated once across three trials — and wired half as much. A
stronger reviewer did not reliably stop a cheaper executor from inventing; the
full council stack consistently beat the reviewer alone and produced the best
single artifact of the campaign, at 3.5x solo cost, without beating either solo
arm on that arm's strongest axis.

During grading, instrument defect #30 was caught before the verdict: the binding
checker counted real endpoints carrying query strings as invented URLs, which
would have tripled one arm's fabrication count. The corrected instrument was
recalibrated before regrading. The second half (a correctness family with a
rank-4 oracle) remains pre-registered and unrun.

---

## The meta-result

Across the whole programme, in every campaign, on every family:

> **The instrument is wrong more often than the work is.**

The 2026-07-21 session alone produced **eighteen defects in instruments and none
in the work they were grading.** The dangerous ones were not the crashes. They
were the ones that produced entirely plausible numbers:

- A predicate whose word boundaries had been written into the source as literal
  backspace bytes. It matched a character no document contains, reported PASS for
  its entire life, and made every document it touched look checked.
- A test-runner path that ran the project's public suite alongside each check, so
  a check's verdict depended on a suite it had nothing to do with.
- A ground-truth query with an unwritten date filter that discarded 947 real rows
  and understated an archive by twenty-seven years.
- Two successive layout predicates that came back green on a build with a
  visible clipping defect.
- An oracle detector that offered a *deliberately broken fixture repo's* passing
  tests as "the repository's own suite" — rank 4, and non-existent.
- Overlapping globs that summed their matches, so an evidence line reported 51
  test suites where 27 exist.
- A fingerprint file overwritten by a background job eight minutes **after** the
  comparison had been made with it.

This is why the highest-value mechanism in this repository is not the loop and
not the router. It is `calibration_gate`: **refusing to grade until the
instrument has proved it can tell known-good from known-hollow.**

---

## What is measured, what is wired, what is neither

| mechanism | status |
|---|---|
| diff-derived predicates + forcing loop | **measured positive**, two families |
| refusal to grade without calibration | measured by construction; caught 5 defects |
| uncovered-first reporting | reporting change; no correctness claim made |
| mechanical extraction of host rules | **measured positive**, one family, one axis |
| data-provenance fact ledger | validated on one deliverable; 100% oracle independence |
| cost router (profile → model) | **wired, n=1, unmeasured** |
| execution-strategy declaration | recorded; **no outcome correlation yet** |
| support council | candidate only; never shipped enabled |
| mode ladder | **measured zero**; retained as scoping only |
| self-authored check admission | **measured zero** correctness lift |
| notes as code | **measured zero**; retired |

Nothing in the "measured zero" rows was deleted. They are kept, labelled, so the
next person does not spend two months rediscovering them.

---

## Release history

| release | what changed |
|---|---|
| 0.4.0 | lean verification loop (schema 4.1); first envelope measurement |
| 0.6.0 | correctness-lift framing **retracted** after the null replicated twice |
| 0.6.1 | relational predicates (`oracle_cli derive --relational`) |
| 0.6.2 | verdict promoted; recipe replicated on a second family |
| 0.6.3 | provenance rank, oracle independence, uncovered-first report, calibration gate |
| 0.6.4 | oracle asked **before** mode; execution strategy declared; model resolution wired |
| 0.6.5 | fact ledger, host-rule extractor, ownership rule under test |

Full per-release detail, including what each one refused to claim, is in
[`Runtime/stable/manifest.json`](Runtime/stable/manifest.json).

---

## Reproducing any of this

Run records live in `Evals/runs/<run-id>/`, each with the prompt, the provider
execution record (model actually used, tokens, cost, isolation), and a
`workspace-fingerprint.json` listing every file the run produced with its sha256.

The bulky workspace trees were pruned on 2026-07-21 after eight of them were
found to contain copied production credentials inside a cloud-synced folder. The
fingerprints remain, so any claim about a removed file is still checkable against
its hash.

```
python Evals/tools/prune_runs.py        # the pruning tool, dry-run by default
```
