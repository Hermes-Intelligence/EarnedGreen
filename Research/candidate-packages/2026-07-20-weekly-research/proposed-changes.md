# Proposed Changes — 2026-07-20-weekly-research

> **NOTHING IN THIS FILE HAS BEEN APPLIED.** This is a reviewable diff plan for a candidate that ends at `awaiting-eval`. `Runtime/stable/`, `Core/`, `Claude/BOOTSTRAP.md`, `Codex/BOOTSTRAP.md`, global pointers, sibling repositories, `Research/sources/registry.json`, `Models/providers.json` and Git history were **not** modified by this run. Promotion is a separate, human-approved step gated on `eval-plan.json`.

## 1. Apply the source-registry patch

**File:** `Research/sources/registry.json` · **Patch:** `source-registry.patch.json` · **Gate:** EV-01, EV-02

| Action | Count | Notes |
|---|--:|---|
| add | 52 | 24 promoted from `pending-review`, 28 newly discovered |
| update | 17 | tier/cadence refresh + `last_checked` bump |
| retire | 8 | dead, redirect-duplicated, or derivative |

This clears the 47-entry `pending-review` backlog inherited from the Claude-v1 migration, so future runs begin from a reviewed inventory. The 28 newly discovered sources enter on a single pass and should be re-checked at their first due date (see Risks in the report).

### Retirements worth reading before approving

- **`claude-v1-code-claude-com-docs-en-agent-loop`** — returns **HTTP 404**; content moved to `https://code.claude.com/docs/en/agent-sdk/agent-loop`.
- **`claude-v1-developers-openai-com-codex-hooks`** — resolves only via **308 redirect** to `https://learn.chatgpt.com/docs/hooks`, which is already a separate registry entry (duplicate).
- **`claude-v1-github-com-openai-codex-issues-16068`** — **closed as a duplicate of #16033**; dead as a tracking target. Track #16033 instead.
- **`claude-v1-amux-io-guides-ai-agent-sandboxing`** — **HTTP 403** on fetch; cause ambiguous (bot filtering vs removal), so it is retired rather than trusted.
- Three practitioner posts (`kunalganglani`, `explainx.ai`, `tembo.io`) — derivative of tier-1 docs, uncited third-hand statistics, or materially stale.

## 2. Repair a dead link in a repository document

**File:** `Claude/OPERATING_CONTRACT.md`, **line 32** · **Gate:** EV-03

The line cites `https://code.claude.com/docs/en/agent-loop`, which **now 404s**. Replace with `https://code.claude.com/docs/en/agent-sdk/agent-loop`.

This was *found* by this run (the URL was fetched and observed to 404), not assumed. It is the only in-repo document citing a retired URL.

## 3. Reconcile version drift in the operating contracts

**Files:** `Claude/OPERATING_CONTRACT.md`, `Codex/OPERATING_CONTRACT.md`, `Setup/*-cheatsheet.md` · **Gate:** EV-04

Both contracts were written against **Claude Code v2.1.205** and **Codex CLI ~0.144.3**. Since the 2026-07-12 baseline:

**Claude Code → v2.1.215** (2026-07-19). Contract-affecting changes:

| Version | Change | Why it matters |
|---|---|---|
| 2.1.211 | Auto mode now permits pushing to **any** branch, including the default branch, without a prompt | Loosens a safety default the contract describes; security-relevant |
| 2.1.210 | Permission classifier runs on **Claude Sonnet 5** by default rather than following `/model` | Changes behaviour the contract attributes to the session model |
| 2.1.210 | Hook-callback timeout was being misreported to the model as a user rejection (stalled unattended sessions) — fixed | Directly affects the contract's loop/hook guidance |
| 2.1.208 | `rm -rf /` and `rm -rf ~` circuit breaker extended to command substitution `$(...)`/backticks and process substitution `<(...)` | Strengthens a guard the contract cites |
| 2.1.207 | `CLAUDE_CODE_ENABLE_AUTO_MODE=1` no longer required on Bedrock, Google Cloud Agent Platform, Microsoft Foundry, Claude apps gateway | Env-var guidance is now wrong for those surfaces |
| 2.1.200 | `default` permission mode relabeled **Manual**; `manual` accepted as an alias | Contract/cheatsheet terminology is stale |
| 2.1.198 | Subagents run in the **background by default** | Changes orchestration guidance |
| 2.1.179 | `teammateMode` default flipped `auto` → `in-process` | Upgraded sessions behave differently than documented |
| 2.1.178 | `TeamCreate`/`TeamDelete` tools **removed** | Any guidance naming them is dead |
| — | Task tool `mode` parameter **deprecated and ignored**; subagents inherit the parent session's permission mode | Contract implies per-subagent mode control |

**Codex CLI → 0.144.6** (2026-07-18); a `0.145.0-alpha` line is iterating fast. Notably, **no changelog entry on or after 2026-07-12 touches hooks, `config.toml`, `AGENTS.md`, `project_doc`, trust or `requirements.toml`** — so the Codex contract's hook/config sections remain accurate. The one substantive item: **0.144.6 corrected the context windows for GPT-5.6 Sol, Terra and Luna to 272,000 tokens** — any context-budget arithmetic in the repo must be re-derived.

> **Unresolved inconsistency to settle at promotion:** two buckets reported different "current" Claude Code releases — **v2.1.215** (changelog top entry) vs **v2.1.214**. Pin the exact release from the changelog before promoting any version floor.

## 4. Model catalog — reviewed, deliberately NOT patched

**File:** `Models/providers.json` · **Status:** no patch proposed this run

The catalog was regenerated **2026-07-19** and **expires 2026-07-26**, so it is in-date and no refresh is due. A provider-side change *was* detected (the 272,000-token context-window correction above), but that is a **model fact requiring tier-1 confirmation against official model documentation**, and this run will not write speculative model data. Per the runbook, volatile model IDs are never fabricated.

**Action:** verify the corrected context windows against official provider docs and fold them into the catalog refresh due **before 2026-07-26**. Recorded in open questions.

## 5. Documentation consistency fixes

| # | File | Problem | Proposed fix |
|---|---|---|---|
| 1 | `README.md` | States no real weekly candidate has completed, but candidates exist (2026-07-14, 2026-07-16, and now 2026-07-20) | Update status text to reflect completed candidate runs |
| 2 | `Research/engine/new-candidate.ps1` | The runbook requires a dated `Research Outputs/YYYY-MM-DD/` copy, but the initializer only creates the candidate directory | Either create the dated output directory in the initializer, or amend the runbook so the requirement matches the tool |
| 3 | `Research Outputs/README.md` | Calls the newest report "the current state of the world" — misleading when the newest report is an **unpromoted candidate** | Reword to distinguish promoted Stable from `awaiting-eval` candidates |
| 4 | `Claude/commands/weekly-hygiene.md` | Weekly hygiene exists but is not invoked by `/weekly-research` | Either call it from the runbook or state explicitly that it is a separate manual step |
| 5 | `workstreams/current.json` | Blocker says *"Models/providers.json catalog expires 2026-07-19"*, but the catalog was regenerated 2026-07-19 and expires **2026-07-26** | Update the stale blocker; it currently reads as an overdue action that is not overdue |

Item 5 was found by this run's preflight. Items 1–4 were raised by the owner and are recorded here so they travel through the same review gate rather than being silently patched.

## 6. Reconcile the 31 `corrected` claims against contract text

**Gate:** EV-04

31 claims came back `corrected` — substantially right but wrong in a detail. Before promotion, diff each `corrected_statement` against the corresponding assertion in both operating contracts and either fix the contract in the promotion diff or record an explicit deferral with a reason.

## 7. A note on tier discipline (evidence that the rule earns its keep)

All 4 rejected claims failed on the **tier rule** — a version-sensitive claim lacking a current tier-1 primary source — not on being shown false; the verifiers recorded that distinction explicitly. Separately, the hooks bucket found tier-5 practitioner content asserting a `PreToolUse` field (`modifyInput`) that does not exist in the tier-1 documentation. Keeping tier 4–5 as leads-only demonstrably prevented a wrong mechanic from entering guidance.

## Explicitly not proposed

- No change to `Runtime/stable/`, `Core/`, either `BOOTSTRAP.md`, or the Router catalog.
- No change to adaptive tooling, fixtures, or eval harnesses.
- No provider-backed benchmark spend (see `eval-plan.json` — this candidate is acceptable on zero-provider checks).
- No commit, push, branch, or remote operation.
