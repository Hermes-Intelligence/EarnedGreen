# Proposed changes — reviewable diff plan (run 2026-07-16-163434)

Candidate only. Nothing here is applied. Research does not edit Stable, does not commit and does not push. Status ends at `awaiting-eval`.

The headline of this run is not a new practice to adopt. It is that **the external literature caught two real problems in what we shipped today**, and the fix list below is mostly ours, not the world's.

## P0 — Fixture validity: repair the medi-ny provenance leak

**Finding:** `public/sample/build_sample.py` ships in every agent workspace. Its docstring names the shipped fix's functions (`_clean_drug_name`, `_form_vocab`), the exact Hermes commits (`9835c408..a7ed0fd1`), and states that ground truth is the shipped parser's behaviour asserted by `hidden/grade.py`. The 100-scoring solution names its function `_clean_drug_name` — matching the leaked name.

**Why it matters:** this leaks the *shape* of the solution. It does not leak the implementation or the expected outputs, and it was present for **all arms equally**, so the 77-vs-100 delta is unbiased. But absolute scores are inflated relative to a genuinely cold task, and the fixture's claim to be a clean shadow-replay is weakened.

**Proposed change** (candidate `2026-07-14-adaptive-agent-modes-v2`, fixture `mode-boundary-fixture-medi-ny`):

1. Move the provenance docstring out of `public/sample/build_sample.py` into a fixture-private note (`hidden/` or the fixture contract). The shipped copy keeps only what a workspace legitimately needs: how to rebuild the PDF.
2. Re-run the admission gate (reference must still score 100, before-parser 27).
3. Re-run **one** arm (owner-approved, 1–3 calls) to confirm the 77→100 delta survives the repair. If it does, the result hardens; if it collapses, we were partly measuring a hint.

**Not proposed:** invalidating the campaign. The comparison is arm-symmetric; only the absolute number is in question.

## P0 — Documentation: state the scope of the scaffolding null correctly

**Finding (C-2026-07-16-003):** varying control-flow *architecture* moves GAIA accuracy up to 28 points within one model. Our null is about *prompt-text* scaffolding.

**Proposed change:** `Setup/benchmarking/verification-loop-results.md` and `Setup/adaptive-modes.md` already say "prompt scaffolding" throughout — **verify and keep**. Add one sentence recording that architectural scaffolding is a different variable with measured positive effects, so nobody reads our null as "scaffolding does not work". A small edit that prevents the document being refuted on sight.

## P1 — Documentation: cite the external corroboration and the external critiques

**Proposed change** to `Setup/benchmarking/verification-loop-results.md`:

- Cite [Compact Constraint Encoding](https://arxiv.org/abs/2604.07192) beside our null: 11 models, 830+ invocations, no significant compliance difference, ~71% token reduction. Our finding replicates independently.
- Cite [Is Three the Magic Number?](https://arxiv.org/abs/2607.05197) beside our iteration ceiling of 3, which we had set from local evidence only.
- Add an **"Answering the strongest critique"** section for [Rethinking Harness Evolution](https://arxiv.org/abs/2607.12227) (submitted 2026-07-14). Its matched-budget demand is **answered from data we already paid for**: three independent vanilla samples cost ~883k tokens and never exceeded 77 (all three failed identically), while a single guided loop reached 100 at 647k–1.21M. At comparable-or-larger spend, best-of-N never finds what one guided iteration finds. Its same-task-tuning critique **stands** and is recorded as an obligation.
- Add [SpecBench](https://arxiv.org/abs/2605.21384) to "What we do not know", with our two verified defences stated honestly: the grader is held out (the agent never sees `hidden/grade.py`), and a hardcoding probe on the winning solution found zero drug-name literals — it is a general implementation (regexes, vocabulary, brand-case recovery, 365 lines). Residual risk: visible checks and the hidden grader exercise the same single sample.
- Add [PBT-Bench](https://arxiv.org/abs/2605.15229): agent-derived property checks miss 17–58% of seeded bugs. Our property checks are a partial net; do not overclaim.
- Add [The Verification Horizon](https://arxiv.org/abs/2606.26300) as a scope boundary: digest-freezing buys integrity *within* a task and forfeits co-evolution *across* generations.

## P1 — Knowledge base: one narrow correction

**Proposed change** to `Research/knowledge-base/2026-07-12-findings.md`, line 5 (Codex tuning keys):

- **Wrong today:** "`[tools] web_search=true` (off by default)".
- **Correct:** there are two distinct keys. Top-level `web_search` is an enum `disabled|cached|indexed|live` defaulting to `cached` (an OpenAI-maintained index, no external access) — and to `live` under `--yolo` or another full-access sandbox. Separately `[tools] web_search` still exists and still accepts the legacy boolean, plus an object form (`context_size`, `allowed_domains`, `location`).
- **Do not delete the `[tools]` entry** — the first researcher's stronger claim was overstated and the verifier caught it.
- **Consequence for us:** a benchmark that assumed search was off has been getting a cached index. Worth knowing; no campaign conclusion depends on it.

**Explicitly NOT changed** (verified already correct, flagged as false alarms): the profiles entry already documents the 0.134.0+ separate-file form; the hooks entry already lists the full event set and already mentions `hooks.json`.

## P1 — Model catalog refresh (due 2026-07-19)

Full proposal in [`model-catalog.patch.json`](model-catalog.patch.json). Summary:

- **No model released, renamed or deprecated 2026-07-12..2026-07-16.** Every live selector remains valid. This refresh is not a model swap.
- **MC-02 (fix):** both `openai-codex` `official_sources` 308-redirect; rewrite to `learn.chatgpt.com`.
- **MC-03 (owner decision):** `current-frontier-creative` has no official backing — OpenAI publishes no creative tier. Keep it as an explicit `aliases_of: current-frontier-coding` with `distinctness: unverified`, or drop it and let `creative-design` be unsatisfiable on that provider. Recommendation: keep-as-alias, marked.
- **MC-04 (record):** availability gates worth surfacing — Fable 5 excluded under zero data retention; CLI version gates; **alias resolution differs per platform** (`sonnet` → Sonnet 5 on the Anthropic API but Sonnet 4.5 on Bedrock/Vertex), which matters because our catalog calls these "provider-current-alias"; `speed:"fast"` on Opus 4.7 errors after **2026-07-24**, inside the proposed window.
- **MC-01 (BLOCKED, no code change):** the `haiku` + `effort: low` recommendation may be invalid — Haiku 4.5 is absent from the affirmative effort-support list, but no page states it is unsupported. The verifier refused the argument from omission. **Settle with one API call** (`claude-haiku-4-5` + `effort: low`): HTTP 400 → the recommendation breaks runs and `resolve_capability_profile` must omit effort for unsupported selectors; silently ignored → merely misleading, a catalog note suffices.
- **MC-05 (record only):** Codex effort levels contradict across two official pages (`config-reference` says `minimal..xhigh`; the changelog announces `max` for Bedrock). Encode only the config enum; recheck next week.

## P2 — Harness improvements worth evaluating (not adopted blind)

- **`codex exec --ephemeral --ignore-user-config --ignore-rules`** for campaign runs (C-2026-07-16-013). Our campaigns are Codex-side, so this is the applicable hermetic lever. **Verifier correction:** these are *narrower* than Claude Code's `--bare` — they do not skip skills/plugins/MCP/memory, and `--ignore-user-config` covers only `$CODEX_HOME/config.toml`. Document them as what they are.
- **`claude --bare`** (C-2026-07-16-012) if we ever benchmark Claude Code: skips hooks/skills/plugins/MCP/memory/CLAUDE.md discovery and becomes the `-p` default in a future release. **Caveats:** only Bash + file read/edit tools survive, and Anthropic-direct auth must be `ANTHROPIC_API_KEY`/`apiKeyHelper`.
- **Codex hook trust gate** (C-2026-07-16-016): repo-local `.codex/` hooks load only when the project layer is trusted — a governance harness shipping repo-local hooks silently no-ops on a fresh CI clone. Our enforcement is Claude-side today, so nothing is broken; record the constraint before any Codex-side hook work.

## Rejected — recorded so they are not re-proposed

See [`rejected-claims.json`](rejected-claims.json). Twelve entries, including three the verifier downgraded and three the researchers found unlocatable or fabricated. Highlights:

- **"Rename `--permission-mode default` to `manual`"** — REFUTED. Only the UI label changed; the config value is still `default`, and `manual` is an alias requiring v2.1.200+. The edit would have been no-op churn at best and breaking at worst.
- **Cost telemetry** (`total_cost_usd`, Codex `turn.completed.usage`) — not actionable yet: one undocumented sentence and an issue-tracker thread respectively. Confirm empirically before touching spend accounting.
- **"LLMs cannot self-correct"** — a 2023 result with no 2026 re-test. Citing it would repeat the expiring-assumption error our own corpus warns about.

## Expected impact

Low risk, high honesty. Nothing in this run changes how the environment behaves at runtime. It repairs one fixture defect, corrects one KB line, refreshes an expiring catalog with no model changes, and — most importantly — **attaches external evidence to claims we had only measured locally**, while recording two live critiques of our own headline result. The single highest-value follow-up is the P0 leak repair plus a confirmation run.

## Rollback

Nothing applied; rollback is deletion of this candidate directory. If any part is later promoted, `tools/promote-candidate.ps1` writes the reversible manifest and `Runtime/releases/<version>/` as usual.
