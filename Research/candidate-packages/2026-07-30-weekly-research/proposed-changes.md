# Proposed Changes - 2026-07-30-weekly-research

> **NOTHING HERE HAS BEEN APPLIED.** Reviewable diff plan for a candidate ending at `awaiting-eval`. No edits to `Runtime/stable/`, `Core/`, bootstraps, global pointers, sibling repos, `Research/sources/registry.json`, `Models/providers.json`, or Git history. Promotion is separate and human-approved, gated on `eval-plan.json`.

## 0. SECURITY NOTICE - one bucket under mandatory review (EV-SEC)

The auto-mode monitor flagged the **`claude-hooks-permissions`** research **and** verify agents as possible "systematic reconnaissance into the classifier's own internals." Assessment: the bucket's task was to document Claude Code's permission/auto-mode mechanics (deny-vs-classifier ordering, exit codes, protected-path/branch rules) for the contract's Permissions section, fetched from **official `code.claude.com` docs** for defensive purposes - almost certainly a false positive. Handling: its **24 claims are tagged `security_review_required`** in `claims.json` and MUST be cleared by a human before informing any promoted text. They are not used silently.

## 1. Model-catalog refresh (the catalog EXPIRED 2026-07-26) - candidate providers patch

`models-providers.patch.json` captures 33 official-doc-verified model facts. **Do not write these into `Models/providers.json` from research** (EV-MODEL re-verifies each at promotion). Headline changes since the catalog was last generated:
- Claude flagship is now Opus 5 (claude-opus-5); Opus 4.8 (claude-opus-4-8) is now LEGACY; Opus 4.1 deprecated, retires 2026-08-05.
- Claude effort levels: low|medium|high|xhigh|max (high=default). 'ultracode' is a Claude Code SESSION setting (sends xhigh + orchestrates dynamic workflows), NOT an API effort level.
- OpenAI/Codex: GPT-5.6 Sol/Terra/Luna (1.05M ctx, 128K out); Codex CLI 0.146.0 (2026-07-29). platform.openai.com/docs/models now 301-redirects to developers.openai.com/api/docs/models.

The most repo-relevant: **`ultracode` is a Claude Code session setting** (it sends `xhigh` effort AND has Claude orchestrate dynamic workflows) - **not** an API effort level. Any repo text treating `ultracode` as an effort value should be corrected.

## 2. Version drift to pin in the contracts (EV-COR + reconciliation)

- **Claude Code -> v2.1.220** (from the raw changelog on 2026-07-30). This resolves last week's unresolved "2.1.215 vs 2.1.214" ambiguity: pin **v2.1.220**. (Corrected detail: the changelog is NOT gapless - 2.1.213 and others are absent - so do not infer contiguous version numbering.)
- The v2.1.212 per-session caps (subagent spawns, WebSearch calls; both default 200) are **confirmed against the raw changelog + tools-reference**, correcting last week's tentative v2.1.199 attribution.
- The `/loop` hide-from-`/resume` fix is **v2.1.211**, not v2.1.178 (last week's guess corrected).
- **Codex CLI -> 0.146.0** (2026-07-29; agent-plugins/marketplace, thread pinning), with 0.147.0-alpha.2 already out.

## 3. Permission footguns surfaced by the Reddit lane (corroborated to tier-1)

Community reports, each corroborated against the changelog before acceptance, worth reflecting in the Claude hooks/permissions guidance:
- **v2.1.214** fixed single-segment `dir/**` allow rules (e.g. `Edit(src/**)`) that were auto-approving writes to `dir/` **anywhere in the tree**. Guidance recommending such rules on pre-2.1.214 is unsafe.
- **v2.1.210** added a startup warning that `Write(path)`, `NotebookEdit(path)`, and `Glob(path)` permission rules are **ineffective** - use `Edit(path)`/`Read(path)`.

## 4. Apply the source-registry patch

`source-registry.patch.json`: **67 add** (24 promoted from pending-review, 43 newly discovered incl. 7 new papers + changelog/tools-reference/model-doc pages), **5 update**, **1 retire** (codex issue #8759 - a bug report filed against an old codex-cli line).

## 5. What the academic deep-dive implies for the repo's own doctrine

The papers are external, quantified corroboration of this repo's measured direction (self-authored checks are weak; diff-derived/deterministic oracles win):
- **arXiv 2607.05904**: self-play drives a judge's pass rate 0.72->0.94 while true accuracy stays flat; a Min-ensemble of 3 judges still accepts **55%** of hacked answers; blind-solve de-anchoring cuts false positives 0.719->0.012. Directly supports "don't let the agent grade itself."
- **arXiv 2606.26300 (Verification Horizon)**: pairing a quality judge with trajectory hack-monitoring cut hacked-resolved from 28.57% to lower - no single-signal silver bullet, matching the repo's layered-oracle stance.
- **arXiv 2605.21384 (SpecBench)**: the visible-vs-holdout pass gap grows **~28pp per 10x code volume** - scale makes reward hacking worse, arguing for held-out oracles at scale.
- **Sourcegraph CodeScaleBench**: every verifier must pass a **Null / Golden / Adversarial** calibration triad before release - an independently-published twin of this repo's vacuity-gate + adversary + necessity-probe admission machinery. Worth a direct diff (recorded as an open question).

These are candidate references, not stable claims; they belong in the knowledge base at promotion, and the CodeScaleBench admission triad deserves a head-to-head against `tools/adaptive` before any doctrine change.

## Explicitly not proposed
- No change to `Runtime/stable/`, `Core/`, bootstraps, Router catalog, adaptive tooling, or the live model catalog.
- No provider-backed benchmark spend (this candidate is acceptable on zero-provider checks).
- No commit, push, or remote operation.
