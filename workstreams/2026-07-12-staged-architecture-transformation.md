# Staged Architecture Transformation

**Status:** in progress

## Goal

Transform the Claude v1 research prototype into a staged, measurable operating system with Stable/Candidate separation, Objective Integrity, deterministic knowledge routing, evals, durable sources and linked PDFs.

## Completed evidence

- Claude v1 ZIP snapshot and SHA-256 created beside the repo.
- 31-requirement objective ledger across nine pillars and failing-on-incomplete checker created.
- Minimal Stable Core, precedence, generalization and change-impact policies created.
- Deterministic Router created; routing suite passed 12/12 cases.
- `init` proved content-preserving and byte-idempotent on a mock repo.
- `doctor` runs on Windows and reports OneDrive/missing dependency/context-size risks.
- Global and five sibling-repository pointers switched to the minimal Stable manifest; VextrumFrontend local rules preserved.
- Research now initializes candidate packages and preserves the Stable hash.
- Durable 21-source registry includes official, academic, benchmark, security, YouTube, podcast and practitioner/social lanes.
- Recovered all 47 unique Claude-v1 URLs into a pending-review migration inventory; candidate snapshots now contain 68 unique URLs and do not rediscover them.
- Added eight provider-independent capability profiles, an expiring provider catalog and recommendation-only model resolver with official provenance.
- Model-profile routing suite passed 10/10, including unsafe downgrade rejection; Knowledge Router remains 12/12; `doctor` reports zero failures.
- Added an outcome adapter record schema that keeps hidden graders outside the agent-visible workspace and records actual model, effort, cost and timing.
- Added tested candidate promotion and rollback, bounded loop checkpoints, structured handoff validation and a unified infrastructure release gate.
- Added two executable pilot fixtures. Starter implementations pass public tests but fail hidden tests; host-only reference solutions pass at 100%.
- Expanded the outcome suite to twelve distinct executable fixtures. The final four-phase harness passed 12/12: public starter pass, hidden starter rejection, public reference pass and hidden reference pass.
- Hardened the validator with per-phase process timeouts, fixture filtering and failure diagnostics. A bounded timeout is accepted only as hidden rejection of a flawed negative control; it remains a hard failure for public or reference phases.
- Re-ran the complete infrastructure gate after fixture expansion: 11/11 checks passed, including 12/12 fixture discrimination and zero JSON or PowerShell parse errors.
- Installed Codex CLI 0.144.1 under WSL, completed device authentication and verified user+mount namespace isolation; infrastructure release gate passed 11/11.
- Added a two-level startup preflight: fast `core` checks for every substantive session and live provider/authentication/isolation checks in `benchmark` mode.
- Added a machine-readable, validated current checkpoint at `workstreams/current.json`; normal restarts now resume without repeating setup or login.
- Quickstart is one visually verified page.
- Transformation report has 20 unique PDF URI annotations and passed visual inspection.
- Created a fresh dedicated `AgenticBench` WSL2 distribution without cloning the existing Ubuntu or copying personal provider homes.
- Hardened `AgenticBench`: one unprivileged user, home mode 700, no sudo, no Windows interop, no mounted C: drive, fixed root-owned runner and host-only hidden grading.
- Installed Codex CLI 0.144.3 and Claude Code 2.1.207 dynamically inside the dedicated distro; no API keys or credentials were written to the repo.
- Added idempotent clone setup, runtime sync, doctor, weekly local provider snapshot and a secret-hygiene gate.
- Added a bounded subscription campaign with explicit 4 -> 8 -> 24 -> 40 approvals, fixed run/turn/time/failure ceilings and `Evals/local/STOP`.
- Proved campaign mathematics and fail-closed approval without starting a provider; tested public workspace transfer and rejected a credential-path symlink.
- Regenerated the benchmark handbook and quick reference PDFs. Visual QA passed all eight rendered pages; the handbook contains 10 unique clickable source targets.
- Re-ran the infrastructure gate: 12/12 passed, including 133 JSON files, 45 PowerShell files and 317/317 secret-hygiene paths.
- Turned the plural `credentials`/`secrets` routing miss into a regression test; runtime controls now pass 5/5.
- Executed the first subscription-backed smoke as an infrastructure shakeout. The audit found five actual provider invocations, including two overlapping campaign attempts and one orphan created by a campaign-state race; all affected attempts were retained and marked invalid, and the campaign was permanently closed as non-publishable.
- Added exclusive campaign and provider locks, orphan-process refusal, explicit invalidation/quarantine/diagnostic-closure records, and a fail-closed recovery path that requires fresh human approval before replacements.
- Corrected enforcement semantics: existing task/public-test files are immutable, new regression tests are allowed, generated Python cache files are ignored, and deleted protected inputs are detected.
- Added provider-event model telemetry. Unreported defaults are recorded as `unresolved-provider-default`; every post-smoke stage now requires an explicit model snapshot.
- Added a four-case benchmark-safety regression suite. The post-incident infrastructure gate passed 13/13, including lifecycle 3/3, fixture discrimination 12/12 and secret hygiene 336/336.
- Regenerated Benchmarking Handbook v0.3 and the quick reference from a reproducible local renderer; visual QA passed all six pages and the handbook contains 10 unique clickable source targets.
- Completed the repaired four-call smoke with exactly four sequential provider executions and no replacements: Claude full, Codex vanilla, Codex full and Claude vanilla all passed public tests, hidden grading at 100/100 and applicable enforcement. There were zero overlaps and zero invalid attempts.
- Recorded the honest smoke conclusion as INCONCLUSIVE: one trial per provider/arm cell and a 100% ceiling cannot establish full-arm lift. Codex provider-default also did not expose an exact resolved model, so post-smoke spend remains blocked on an explicit model snapshot and fresh human approval.
- Added deterministic campaign summarization and generated structured JSON, Markdown and a visually verified one-page smoke PDF. The report records the useful existing-test edit made by Codex vanilla and the separate regression files created by full arms.
- Resolved future provider selectors without inference or Stable edits: the weekly-expiring local snapshot pins Codex `gpt-5.6-sol`/medium and Claude `claude-opus-4-8`/medium from current official and retained provider evidence.
- Generated a structured Markdown/JSON/two-page PDF provider-resolution report. Visual QA, PDF EOF/text extraction and all three clickable official-source annotations passed.
- Prepared campaign `20260713-151556-calibration-probe`: exactly two unapproved, randomized Codex calls on the harder migration fixture, vanilla versus Core+Router+enforcement. It is screening-only, non-publishable and cannot automatically unlock further spend.
- Caught and fixed a case-insensitive PowerShell parameter/local-variable collision before any provider call. The new end-to-end regression proves exact two-call pending-manifest generation; benchmark safety passes 5/5.
- Re-ran the full gate: 16/17 technical/objective checks pass. The sole failure is intentional and truthful: 24 objective requirements remain open and require evidence.
- Executed exactly two explicitly approved Codex calibration calls on `gpt-5.6-sol`/medium. Vanilla and Core+Router+enforcement both changed only `src/migration.py`, passed public tests, hidden grading at 100/100 and enforcement, with zero overlaps, invalid attempts, replacements, protected-file edits, Claude calls or later-stage execution.
- Applied the predeclared CEILING rule: both solutions were semantically equivalent idempotent/reversible migrations preserving rows and UNIQUE constraints, so the fixture cannot measure environment lift. All further provider spend is stopped pending a harder deterministically validated fixture.
- Generated structured JSON, Markdown and a visually verified one-page calibration PDF. PDF EOF and required verdict/STOP text checks passed.
- Added the composite `production-ingestion-evolution` benchmark with an open implementation architecture and exact production outcome contract. Its 100-point hidden grader independently scores functional behavior, generalization, reliability, security, edge cases and performance using trial-varying host-only names.
- Proved zero-provider discrimination: starter/hardcoded 46, secure-but-closed 70, generic-stateless 85 and reference 100; every variant passes the public happy path. The full outcome harness now passes 13/13.
- Corrected outcome semantics so a valid partial score is retained as `outcome_valid` without being mistaken for infrastructure failure. Benchmark safety passes 8/8.
- Added provider-event token/cache/output/reasoning telemetry and provider-reported USD capture. Subscription monetary cost is explicitly marked unavailable when the CLI does not expose it.
- Prepared the unapproved six-call campaign `20260713-181006-complex-ingestion-screen`: three paired Codex trials per arm, explicit model/effort, randomized order, zero automatic replacements and no automatic confirmation or Claude stage. Its zero-call predecessor was closed as superseded when a final grading-harness fix changed the pinned hash.
- Generated and visually verified the two-page Complex Production Benchmark Design PDF documenting quality-first comparison and the separately approved 6 -> 10 -> 16 cost ladder.
- Executed exactly six explicitly approved Codex complex-screen calls sequentially: three vanilla and three Core+Router+enforcement pairs on `gpt-5.6-sol`/medium. Audit found six unique campaign run IDs, six provider executions, zero orphans, overlaps, invalid outcomes, Claude calls, replacements or protected-file changes.
- Applied the predeclared `NO_ACTIONABLE_SIGNAL` rule. Both arms scored 95/100 in all three pairs with identical dimension scores and no critical-floor difference. At tied quality, the full arm used 253.1 versus 216.5 median wall seconds and 262,510 versus 215,413 median observed tokens; subscription monetary cost was not exposed.
- Found a common-mode fixture-alignment concern: all six solutions added `index` to skipped duplicates, while the hidden replay check required exact equality without `index` and the public task did not state that exact-field rule equally explicitly. Historical outcomes and pinned grader remain immutable; a future fixture must be versioned, clarified and revalidated locally.
- Added a deterministic complex-screen summarizer and generated structured JSON, Markdown and a visually verified two-page PDF. The report records measurement integrity `PASS`, comparative conclusion `NO_ACTIONABLE_SIGNAL`, resource overhead, interpretation limits and a zero-additional-call STOP decision.
- Re-ran both gates after reporting and checkpoint updates. Infrastructure passed 13/13; the full gate passed 16/17 across 243 JSON files, 55 PowerShell files, 13/13 fixture discrimination, 8/8 benchmark safety and 454/454 secret-hygiene paths. The only red check remains the truthful objective gate with 24 open requirements.
- Added six independent real-world fixtures: multi-file API propagation, an open-world escaped parser, a misleading-green multi-tenant cache, atomic multi-session resume, coordinated code/migration/docs/observability rollout and prompt-injection precedence defense.
- Added two public-green negative controls and one 100-point reference for every new fixture. The complete harness passes 19/19; the new ladders are 10/70/85/100, 25/25/75/100, 20/75/80/100, 15/45/85/100, 5/55/60/100 and 35/55/75/100.
- Added the structured real-world battery protocol, a deterministic campaign generator and a 9/9 lifecycle regression. It proves 12 unique cells staged 6 + 6, zero-call creation, fail-closed later-stage approval, 13 pinned hashes and zero automatic replacements.
- Generated campaign `20260713-201400-real-world-battery-screen` on explicit `gpt-5.6-sol`/medium. It has zero approvals and run IDs and is awaiting separate approval for exactly six sentinel calls.
- Generated and visually verified the three-page Real-World Agentic Environment Battery Setup PDF. EOF and required-text checks pass.
- Final post-battery gates: infrastructure passes 14/14; full passes 17/18 across 273 JSON files, 57 PowerShell files, 19/19 fixture discrimination, 9/9 battery lifecycle, 8/8 benchmark safety and 547/547 secret-hygiene paths. Only the truthful objective-complete check remains red with 24 open requirements.
- Executed exactly six separately approved real-world battery sentinel calls sequentially on `gpt-5.6-sol`/medium. Audit found six unique provider executions, zero orphans, overlaps, invalid outcomes, protected-file changes, retries or diversity-stage calls.
- Applied the predeclared `NO_ACTIONABLE_SIGNAL` sentinel rule. Vanilla and Core+Router+enforcement tied 90/90 on API propagation, 90/90 on coordinated release and 100/100 on resumable sessions, with identical critical-check outcomes. Full used 25.2% more median wall time and 36.6% more median observed tokens.
- Added a deterministic real-world battery summarizer plus structured JSON, Markdown and a visually verified two-page PDF. The campaign is stopped at the separate diversity approval boundary; replication, Claude, Stable promotion and automatic model switching remain unauthorized.
- Post-sentinel infrastructure passed 14/14 across 284 JSON and 58 PowerShell files. The full gate passed 17/18; its sole red check remains the truthful objective gate with 24 open requirements.

## Still open

- Run a real weekly research candidate, reconcile the remaining pre-benchmark objective evidence and make the benchmark-ready gate green.
- Calibrate Router false positives, context-character budget and security recall.
- Run a real candidate research pass through the installed Workflow runtime.
- Migrate individual useful v1 contract claims through claim ledger and eval-backed promotion.
- Generate repository-specific, tested hooks rather than generic templates.
- Update objective statuses only when their full acceptance criteria have evidence.
- One-time OAuth is complete for both providers; AgenticBench doctor passes 12/12 and benchmark preflight passes with zero failures and zero warnings.
- Review the completed sentinel report and decide whether three materially different remaining families justify exactly six diversity calls; replication, cross-provider work and all older larger stages remain disabled.
- Turn the `prompt-injection-repo` security-routing miss into a Candidate regression and evaluate it before any Stable promotion.

## Next

Keep provider spend stopped until the user reviews the `battery-sentinel` NO_ACTIONABLE_SIGNAL report for campaign `20260713-201400-real-world-battery-screen`. If explicitly approved, run only `battery-diversity` with exactly six Codex calls on the three untested families. Keep replication, Claude, directional, confidence, pilot, Stable Router edits and automatic model switching disabled until their distinct evidence and approval gates are satisfied.
