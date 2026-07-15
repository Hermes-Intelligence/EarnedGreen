# Stage 2: Source Recovery, Verification and Model Capability Routing

**Date:** 2026-07-12  
**Status:** implemented and locally verified; no commit or push  
**Authority:** repository changes were user-directed. Research itself remains candidate-only.

## Executive result

The earlier 21-source statement was incomplete. A mechanical provenance audit recovered **47 unique URLs** from Claude's original contracts and research artifacts. All 47 now exist in a dedicated migration inventory with `pending-review` status. Together with 21 reviewed seeds, candidate research begins with **68 unique URLs** instead of rediscovering the same corpus.

The repository now also contains a capability-based Model Router. Stable task policy selects profiles such as fast, balanced, deep implementation, creative design or adversarial review. Provider-specific aliases and availability live in an expiring data catalog rather than in stable prose or routing code. Recommendations are task/session scoped and never silently persist the user's default model.

## What was verified

| Check | Result | What it proves |
|---|---:|---|
| Claude-v1 URL recovery | 47/47 unique | Original links preserved with provenance. |
| Composite source memory | 68 unique URLs | Both inventories merge without exact duplicates. |
| JSON parsing | 26/26 | Structured artifacts parse. |
| PowerShell parsing | 14/14 | Scripts have no syntax errors. |
| Knowledge Router | 12/12 | Required modules are selected. |
| Model-profile Router | 10/10 | Profiles select correctly; unsafe downgrades reject. |
| Doctor | 0 failures | Local diagnostic checks pass. |
| Stable isolation | unchanged SHA-256 | Candidate did not mutate Stable. |

These checks **do not** prove that routed agents produce better production code. That requires repeated outcome trials with isolated fixtures and hidden graders. The new adapter contract records the actual resolved model, effort, timing, cost, changed files and grader evidence so that model-routing claims can be tested rather than assumed.

## Source governance changes

`Research/sources/registry.json` remains the reviewed seed registry. `Research/sources/claude-v1-migration.json` is a complete mechanical recovery of Claude's first-run links. Recovery does not confer trust: every migrated source remains `pending-review` until link availability, authorship, date, relevance and claim-level support are checked.

Every new candidate receives a de-duplicated snapshot of both inventories. Pending sources and due active sources are scheduled before broad discovery. A weekly run proposes changes through `source-registry.patch.json`; it cannot directly edit the reviewed registry or Stable rules. YouTube, podcasts and social/practitioner pages remain a radar for leads, while version-sensitive mechanics and security claims require primary corroboration.

## Model routing design

The model layer separates durable intent from volatile products:

1. The task router determines task type and risk.
2. It selects a provider-independent capability profile and effort level.
3. The Model Router resolves that profile against the current provider catalog.
4. Explicit user choice wins unless it violates a safety/risk floor.
5. The recommendation applies only to the current task, session or subagent.
6. The run records the actual resolved model; aliases alone are insufficient evidence.
7. Catalogs expire weekly and research may only propose a candidate refresh.

The current Anthropic mapping uses provider-maintained aliases such as Haiku, Sonnet, Opus, Fable and `best`; the aliases can move as Anthropic releases models. OpenAI mappings deliberately use capability selectors such as `current-fast` and `current-frontier-coding` rather than embedding a changing product name in policy. The runtime/provider adapter must resolve these against actual availability.

Automatic switching remains disabled. It should be promoted only when controlled A/B trials show equal or better correctness and generalization after accounting for cost, latency and human review time. High-risk architecture, security, destructive migrations and production decisions retain a strong-model floor and human gate.

## Defects found during verification

The first migration attempt exposed the machine's PowerShell execution-policy restriction. The migrator was then validated with an explicitly scoped process-level bypass, and `doctor` now reports the active policy. The first Model Router run also failed because Windows PowerShell compared `DateTime` with `DateTimeOffset`; the code was corrected to use offset-aware time consistently. Two initial model-routing cases failed before correction; the final suite passed 10/10, including rejection of an inadequate risk profile and an incompatible selector.

These failures are retained in the narrative because a verification system should expose and convert its own mistakes into regression checks. Both corrected paths are now exercised by the repeatable local suite rather than relying on the successful rerun alone.

Accordingly, "verified" in this report means that the stated deterministic checks were rerun against the final files. It does not silently broaden into source validation, model-quality proof or production-readiness for unimplemented provider adapters.

## Remaining gates

- Review the 47 migrated sources; they are preserved, not yet trusted or live-checked one by one.
- Build isolated executable fixtures for unseen-entity generalization and objective omission.
- Add provider launch adapters that keep hidden graders outside the agent-visible workspace.
- Run at least five controlled trials per case and arm: vanilla, Core, Core+Router and Core+Router+enforcement.
- Compare correctness, unseen-input behavior, regressions, latency, tokens/cost and human interventions.
- Enable autonomous model switching only if those outcome evals justify it.
- Promote any stable change through a separate reviewed approval and rollback manifest.

## Impact on future work

Agents now start with less context, retain the complete objective, retrieve only relevant rules, preserve all known research sources, and can choose an appropriate capability tier without freezing today's model names into production policy. Just as importantly, the system refuses to treat routing success, attractive documentation or a newly released model as proof of better engineering outcomes.

## Sources

- [OpenAI model catalog](https://developers.openai.com/api/docs/models) — official current model and capability reference, accessed 2026-07-12.
- [OpenAI Codex models](https://developers.openai.com/codex/models) — official Codex model reference, accessed 2026-07-12.
- [Anthropic model overview](https://platform.claude.com/docs/en/about-claude/models/overview) — official current model families, capabilities and Models API guidance, accessed 2026-07-12.
- [Claude Code model configuration](https://code.claude.com/docs/en/model-config) — official aliases, effort, fallback and configuration behavior, accessed 2026-07-12.
- [Evaluating AGENTS.md](https://arxiv.org/abs/2602.11988) — evidence that repository instructions require empirical evaluation, accessed 2026-07-12.
- [Probe-and-Refine Repository Guidance](https://arxiv.org/abs/2606.20512) — evidence for task-probed guidance refinement, accessed 2026-07-12.
- [ContextBench](https://arxiv.org/abs/2602.05892) — evidence for measuring context retrieval precision and recall, accessed 2026-07-12.
- [METR developer productivity study](https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/) — evidence that benchmark performance and experienced-developer productivity can diverge, accessed 2026-07-12.
- [OWASP MCP Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/MCP_Security_Cheat_Sheet.html) — layered trust and tool-security reference, accessed 2026-07-12.
