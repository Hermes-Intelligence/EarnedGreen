# Bootstrap — Agentic Work Best Practices

**Date:** 2026-07-12 · **Status:** 🟢 done (v1 shipped)

## Goal
Stand up `AgenticWorkBestPractices` as the single source of truth governing how every coding agent (Claude Code, Codex) operates across all repos: SOTA, production-grade, self-verifying, well-logged. Deliverables: per-platform operating contracts, shared doctrine, an automated self-resuming research engine, dated PDF reports, human cheatsheets, and automatic propagation to every repo.

## Plan
- [x] Scaffold repo skeleton, charter, `Shared/` doctrine
- [x] Zero-dependency dated-PDF pipeline (headless Chrome), smoke-tested
- [x] Self-resuming research engine (`state.json`, runbook, versioned workflow, `/weekly-research`)
- [x] Maximal multi-agent research (24 agents: research → verify → synthesize)
- [x] Claude + Codex operating contracts + cited knowledge base
- [x] Enrich `Shared/` doctrine with verified practice
- [x] First dated PDF report → `Research Outputs/2026-07-12/`
- [x] `Setup/` cheatsheets (quickstart + per-platform), md + pdf
- [x] Hook/template example scripts
- [x] Global propagation (`~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`)
- [x] Per-repo propagation (5 sibling repos)
- [ ] Push source repo to GitHub (awaiting user confirmation)

## Decisions
- **Propagation by thin pointer**, not copies — one canonical repo; global config + per-repo pointers route agents here, so content edits take effect everywhere instantly.
- **You-triggered weekly research** (`/weekly-research`) over unattended scheduling — keeps a human in the loop; the harness is self-resuming so it reloads context automatically.
- **Zero-dependency PDF renderer** (self-contained md→HTML + Chrome) so the weekly run never breaks on a missing pip package.
- **Research doctrine merged into `Shared/`** as the core, keeping the "binds every agent / stricter-rule-wins" framing and re-adding the prompt-injection rule research omitted.
- **Sibling-repo git left to the user** — pointer files added but not committed (respects VextrumFrontend's "Sebastian does all git" rule).

## Changes
- Repo tree: `Shared/`, `Claude/`, `Codex/`, `Research/`, `Research Outputs/`, `Setup/`, `.automation/`, `.claude/commands/`, `workstreams/`.
- Contracts: `Claude/OPERATING_CONTRACT.md`, `Codex/OPERATING_CONTRACT.md` (11 sections each, source-cited).
- Doctrine: `Shared/{principles,definition-of-done,workstream-logging}.md`.
- Engine: `Research/engine/{state.json,research-brief.md,sources.md,changelog.md,research-workflow.js}`; KB `Research/knowledge-base/2026-07-12-findings.md`.
- Automation: `.automation/md_to_pdf.py` (+ README).
- Outputs: `Research Outputs/2026-07-12/report.{md,pdf}`.
- Setup: `Setup/{quickstart,claude-cheatsheet,codex-cheatsheet}.{md,pdf}`.
- Templates: `Claude/hooks/*.sh`, `Claude/templates/settings.json`, `Codex/templates/{protect-tests.py,config.toml}`.
- Global: `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`. Per-repo: `CLAUDE.md` + `AGENTS.md` pointers in all 5 sibling repos.

## Verification
- PDF pipeline smoke-tested end-to-end (cover, tables, nested lists, code, blockquotes render correctly); report + 3 cheatsheets rendered (113–258 KB each).
- Research run: 24/24 agents completed, 0 errors, 0 empty results, ~2.86M tokens.
- Integration verified: contracts titled + HTML-entity-clean; `state.json` shows 8 topics HIGH + 45 open questions.
- VextrumFrontend `CLAUDE.md` insertion verified — original content and hard rules preserved.

## Status / next
- **Done:** v1 shipped and propagated (working tree ready to commit).
- **Next:** (1) user reviews contracts; (2) push source repo to GitHub (awaiting confirmation); (3) user commits sibling-repo pointer files in their own flow; (4) next `/weekly-research` run targets the 45 open questions.

## Open questions
45 version-sensitive / unresolved items captured in `Research/engine/state.json` (e.g. Codex `model_context_window` regression status, prompt-injection residual risk, native-Windows sandbox parity). These are the backlog for the next run.
