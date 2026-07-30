# Receipts: what we measured, and who found it independently

Every claim this environment makes was paid for in provider calls and registered
before the result was known. This page pairs each measured finding with the
external work that reached the same place by a different road. Where the outside
world contradicts us, that is here too.

Reading order: the claim, our number, their number, and what it changed.

> **Status of the external citations.** Everything under "Theirs" is **secondhand**:
> collected by a research pass, verified against its sources by an adversarial
> verifier stage, and *not* re-checked from this repository. Under this repo's own
> precedence policy, external research is data, never authority — it explains why
> a mechanism is shaped the way it is, and it never substitutes for a measurement
> of ours. Figures quoted inside source comments carry the same status. If you are
> evaluating this environment, verify the identifiers before leaning on them.

---

## 1. A model grading its own work is not verification

**Ours.** Self-authored checks, even after passing a discrimination gate, bought
**zero correctness lift** over a well-configured vanilla arm (all nine runs 92,
`silent_defect_rate` 0.125 across arms). Separately, on the medi-ny campaign the
unforced arm declared "done" in **every** trial while two of eight behaviours
were broken — `silent_defect_rate` 0.25 against the loop's 0.0.
Evidence: `check-admission-ceiling-measured`, `silent-defect-rate-first-measurement`.

**Theirs.** A 2026 study of self-play verification reports pass rates of
**0.72–0.94 where true accuracy is 0.20**, and finds that **ensembling judges does
not rescue it** (~55% acceptance of wrong work)
([arXiv:2607.05904](https://arxiv.org/abs/2607.05904)). A separate systematic
evaluation across **21 judges and ~541k judgments** separates *reliability* from
*validity*: a judge can be highly consistent and still wrong
([arXiv:2606.19544](https://arxiv.org/abs/2606.19544)).

**What it changed here.** Three things, all structural:
* a strong model's review **never** moves a dimension into the earned-green
  column — it is recorded as `reviewed-unverified` and stays in the named column
  (`coverage_manifest.NON_CERTIFYING_PROVENANCE`);
* an approving reviewer must hand back predicates that pass the **same structural
  validator admission uses**, or an explicit *"this cannot be checked
  mechanically"* declaration (the boolean, not any truthy value); bare approval
  and predicate-shaped junk are both refused (`tiered_loop.record_response`).
  A `block` or `revise` verdict does **not** clear the gate — answeredness is not
  agreement;
* we can now **measure our own reviewer** instead of assuming: `reviewer_probe`
  submits flattering hollow work and records whether it gets approved.

Where it bites: the gate calls this (`pre_submit_gate`) only for a workspace that
has a `.agentic/tiered.json` — the tier is opt-in per task, so a repo that never
enables it is unaffected. Predicates a reviewer proposes are validated for shape
at recording time and still face full admission before they can hold anyone to
anything.

---

## 2. Tests that agree with themselves prove nothing

**Ours.** Writing both the implementation and its fixture produced a suite that
certified our own consistency, not the system's behaviour; the discipline that
came out of it is *take the shape from the producer and run it for real*.
Evidence: `tests-that-agree-with-themselves`.

**Theirs.** The same reliability-vs-validity distinction, quantified with a
kappa-deflation figure ([arXiv:2606.19544](https://arxiv.org/abs/2606.19544)).

**What it changed here.** Council **agreement is not evidence**: two strong models
countersigning a memo does not make its invariants right. They enter the suite as
`provisional` and are confirmed only when an accepted implementation satisfies
them.

---

## 3. Prompt-text scaffolding is overhead

**Ours.** Five levels of prompt scaffolding, six fixtures: every arm including
bare vanilla reached the same score; on the one real task `full` matched vanilla
at **10.7× the cost**. Replicated later as a null on two further families.
Evidence: `Setup/benchmarking/verification-loop-results.md`.

**Theirs.** A near-exact independent replication — 11 models, 16 tasks, 830+
invocations, **no significant compliance difference** between verbose and compact
encodings, ~71% fewer tokens
([arXiv:2604.07192](https://arxiv.org/abs/2604.07192)).

**The boundary, stated by both.** Control-flow **architecture** is a different
variable and moves accuracy by up to 28 points within one model
([arXiv:2606.08529](https://arxiv.org/abs/2606.08529)). Our text changes bought
nothing; our architectural change (the loop) bought everything.

---

## 4. The loop's value is real, and it is bounded by difficulty

**Ours.** On two independently measured hard families the full environment beat
well-configured vanilla under pre-registered rules: **88.7 vs 33.3** (non-overlapping
distributions) and **71.3 vs 43.0** (gap 28.3 > the 16-point variance band). On two
easy families every arm saturated and the environment added nothing — which we
published as such. The sharpest regularity across all campaigns: **the loop's floor
equals the bare-canary level, while unforced arms fall below it**.
Evidence: `decisive-campaign-observed.json`, `portal-family3-observed.json`,
`dataflow3-verdict-observed.json`.

**Theirs.** Benchmark-validity work on coding agents documents replay effects and
over-optimization pressure ([arXiv:2607.01211](https://arxiv.org/abs/2607.01211)) —
the reason our fixtures carry an admission gate, a leak audit, and named
ungraded dimensions rather than a single headline number.

---

## 5. More agents is not more quality

**Ours.** Not yet measured — the tiered/council mechanism is built and its
campaign is designed, not run.

**Theirs.** 180 configurations × 5 architectures × 4 benchmarks × 3 model
families: **independent multi-agent systems amplified errors 17.2×**, centralized
ones ~4.4×, with a help/harm split by task shape of **+80.9% / −39…−70%**
([Google Research](https://research.google/blog/towards-a-science-of-scaling-agent-systems-when-and-why-agent-systems-work/);
caveat: no coding task in their suite). Agent teams also cost roughly **7× the
tokens** of a single session.

**What it changed here.** The council ships **disabled by default**
(`council_enabled: False`) — our own rule, that an unmeasured mechanism does not
ship on, applied to our newest mechanism. The review tier stays on; a stall
degrades to a single strong review instead of a council, and a budgeted
self-request is served by a review too, so there is no back door into the
council while it is off. And the cost prior is written into the campaign's
pre-registration: **the full tiered stack may well lose on cost**, and we said so
before spending.

---

## 6. Agents will satisfy the letter of a check

**Ours.** Over-constraint and its inverse appeared repeatedly: instruments that
pinned a reference's incidental choices (aliases, write verbs, value quirks) and
graded real work as zero. Three instrument generations on one family before it
was valid.
Evidence: `dataflow2-replication-observed.json`.

**Theirs.** Reward-hacking benchmarks for tool-using agents measure per-model
exploit rates, ~72% CoT-monitor coverage, and a **measurable environment-hardening
effect** ([arXiv:2605.02964](https://arxiv.org/abs/2605.02964));
controlled-injection work links judge bias directly to reward hacking
([arXiv:2606.04923](https://arxiv.org/abs/2606.04923)).

**What it changed here.** A new probe we did not have: `capture_adversary` asks an
attacker to make the frozen suite green **with a deliberately hollow
implementation**. A `corpus-fakeable` verdict means the corpus is too predictable
and should be widened before the predicates are trusted. Our whole architecture
rests on the corpus being adequate; until now we had never attacked that
assumption. **Honest scope:** it is a probe you run, not yet an automatic
admission blocker — the fixture-admission gate does not call it, and wiring that
in is queued, not done.

---

## 7. Our admission machinery has an independently published sibling

`sourcegraph/CodeScaleBench` (Apache 2.0) gates verifier admission with a
**null / golden / adversarial** calibration triad and deterministic — not
LLM-judged — scoring. Ours is vacuity gate (null) + divergence-witness adversary +
necessity probe.

Two consequences:
* **validation**: an independent team converged on the same shape, which is the
  strongest outside signal our design has received;
* **a named gap**: for genuinely new work we had no *golden* at admission time,
  because no known-good implementation exists yet. Acceptance is our golden, so
  `oracle_bootstrap.calibrate` runs the full triad retroactively over the
  **proposal** predicates (spec/council/finding) and names which were decoration
  all along. Envelope pins are excluded by construction — they are green on the
  baseline because preserving it is their job, and grading them against a null
  slot would label every one of them decoration and bury the real signal.

An external calibration run against their corpus is queued — the first test of
this machinery on somebody else's benchmark rather than our own.

---

## What we still do not claim

* No measured result on **from-scratch** features: our lift is measured where an
  oracle can be derived (history) or stated (spec). New behaviour with neither
  gets the envelope, the named-unverified column, and a human.
* The tiered loop and council are **implemented and unit-tested, not measured**,
  and only partly wired: the T2 review gate runs from `pre_submit_gate` and
  `awbp review`, while the council protocol, the capture adversary and the
  reviewer probe are libraries you invoke deliberately — no automatic caller
  runs them yet.
* This package was audited adversarially by an independent model, which found
  eight defects including two critical ones (a `block` verdict that unblocked
  done, and mechanisms with no production caller). They are fixed and pinned by
  tests named after the findings; the audit is why those tests exist.
* Everything above is Anthropic-family models on Python and JavaScript
  repositories; nothing here has been run on other providers or languages.
