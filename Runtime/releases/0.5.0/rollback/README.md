# Agentic Work Best Practices

A staged, measurable source of truth for production-grade Codex and Claude work.

## Active architecture

```text
Stable manifest -> minimal Core -> deterministic task Router -> Context Pack
                                                    -> objective/evidence gates
                                                    -> capability profile -> expiring provider catalog

Research source registry -> candidate package -> evals -> human approval -> promotion
```

Active global and repository pointers load only [`Runtime/stable/manifest.json`](Runtime/stable/manifest.json), [`Core/runtime.md`](Core/runtime.md), and the relevant platform bootstrap. The long v1 contracts and research corpus are reference material, not always-on instructions.

## Commands

```powershell
# normal new session or restart (agents run this themselves)
powershell -ExecutionPolicy Bypass -File tools/preflight.ps1 -Mode core -TargetRepo <repo>

# first clone setup (installs current Codex in WSL only when requested)
powershell -ExecutionPolicy Bypass -File setup.ps1 -InstallCodex -GlobalPointers

# one-time interactive provider authentication
powershell -ExecutionPolicy Bypass -File setup.ps1 -LoginCodex

# diagnose
powershell -ExecutionPolicy Bypass -File tools/agentic.ps1 doctor -TargetRepo <repo>

# idempotently install/refresh repo pointers
powershell -ExecutionPolicy Bypass -File tools/agentic.ps1 init -TargetRepo <repo>

# compile a task-specific Context Pack
powershell -ExecutionPolicy Bypass -File tools/agentic.ps1 route -TargetRepo <repo> -Task "<task>"

# refuse false completion
powershell -ExecutionPolicy Bypass -File tools/objective-check.ps1

# deterministic routing evals
powershell -ExecutionPolicy Bypass -File Evals/run-evals.ps1 -Mode routing

# infrastructure release gate
powershell -ExecutionPolicy Bypass -File tools/release-gate.ps1 -Mode infrastructure

# live provider authentication and isolation check before paid benchmarks
powershell -ExecutionPolicy Bypass -File tools/preflight.ps1 -Mode benchmark

# validate all 19 fixtures and the six-family real-world battery without provider calls
powershell -ExecutionPolicy Bypass -File Evals/validate-outcome-harness.ps1
powershell -ExecutionPolicy Bypass -File Evals/test-real-world-battery.ps1

# create a new unapproved 6 + 6 battery campaign (starts zero calls)
powershell -ExecutionPolicy Bypass -File Evals/tools/new-real-world-battery-screen.ps1

# recommendation only: resolve a capability profile for the current provider
powershell -ExecutionPolicy Bypass -File tools/agentic.ps1 model-recommend -Provider anthropic-claude-code -Profile deep-implementation
```

## Restart and resume behavior

Node, the provider CLI, authentication, global pointers and machine-local setup evidence persist across a normal Windows restart. The platform bootstrap tells Codex and Claude to run the lightweight `core` preflight themselves and resume from [`workstreams/current.json`](workstreams/current.json). You do **not** rerun setup or login after each reboot.

The full setup is needed only on a fresh clone or machine, after revoked/expired authentication, after missing dependencies, or when preflight explicitly returns `setup_required=true`. Immediately before a paid benchmark, the stricter `benchmark` mode rechecks the live provider login and WSL isolation instead of trusting old evidence.

## Weekly research and model refresh

Ask the agent to run the weekly research workflow (in Claude Code: `/weekly-research`). The agent must follow [`Research/engine/research-brief.md`](Research/engine/research-brief.md), so the request automatically includes source rechecks, research radar discovery and provider/model drift review.

For models and providers, every weekly run must:

1. Check whether [`Models/providers.json`](Models/providers.json) is expired or a material provider/model release was detected.
2. Use `tools/model-refresh-plan.ps1` and verify current models, aliases, capabilities, effort levels, deprecations, availability and tool-version gates against official provider sources.
3. Keep stable capability profiles independent of volatile product names. Never invent a model ID or silently change the user's default model.
4. Write the proposed provider catalog only inside the new candidate package, together with provenance, a reviewable diff and required routing/outcome evals.
5. End at `awaiting-eval`. Research must not directly replace the active catalog or Stable rules.
6. Promote only in a separate, explicit, human-approved step after the required evals and rollback review.

If the active provider catalog has expired before promotion, model routing must warn, prefer a provider-maintained current alias when supported, or request refresh. It must not pretend stale availability data is current.

The candidate workflow, dry-run-first `promote-candidate` command and rollback command are implemented. Promotion remains a separately reviewed, explicitly human-approved repository change, never an automatic side effect of research.

## Governance

- Stable changes only through separate, explicit promotion after required evals and human approval.
- Weekly research reuses the reviewed [`registry.json`](Research/sources/registry.json) plus the complete [`claude-v1-migration.json`](Research/sources/claude-v1-migration.json), rechecks due sources, proposes source updates and writes only a candidate package.
- Model selection uses stable capability profiles and expiring provider catalogs. It is recommendation-only until controlled outcome evals demonstrate lift; it never silently persists a user's default model.
- Candidate promotion and rollback are dry-run by default and require explicit `-Approve` plus approver identity. Promotion verifies hashes, required artifacts and eval gates.
- Benchmark protocol and commands are documented in [`Setup/benchmarking/benchmarking-handbook.md`](Setup/benchmarking/benchmarking-handbook.md) and the six-family [`real-world-battery.md`](Setup/benchmarking/real-world-battery.md), each with a matching visually verified PDF.
- Research never edits Stable, global pointers, sibling repos, Git history or remotes.
- Candidate reports end with clickable source appendices and receive visual PDF QA.
- Objective status comes from [`Objectives/active/OBJ-20260712-agentic-work-best-practices.json`](Objectives/active/OBJ-20260712-agentic-work-best-practices.json), not an agent's declaration.

## Current evidence

- Claude v1 preserved as `AgenticWorkBestPractices-Claude-v1-2026-07-12.zip` plus SHA-256 beside the repo.
- Objective ledger: 31 requirements across nine pillars; deliberately incomplete items remain visible.
- Deterministic Router suite: 12/12 mock cases selected required modules.
- Deterministic model-profile suite: 10/10 cases passed, including risk-floor and incompatible-selector rejection; this does not yet prove outcome quality.
- Source memory: 21 reviewed seeds plus 47/47 Claude-v1 URLs preserved as pending review (68 unique URLs total).
- `init` test: existing content preserved, exactly one managed block, identical hashes after the second run.
- Candidate initializer smoke test: Stable manifest hash unchanged.
- Quickstart: visually verified as one page.
- Transformation report: visually verified, three pages, 20 unique clickable source links.
- Stage 2 verification report: visually verified, four pages, nine clickable source links.
- Post-incident infrastructure release gate: 13/13 checks passed after JSON/PowerShell parsing, routing, runtime, fixture discrimination, lifecycle, benchmark-safety, security-hook, Windows/OneDrive, WSL-isolation and secret-hygiene tests.
- Outcome harness: 19 executable fixtures. The original 13 cover focused failure modes and composite ingestion; six new real-world fixtures cover API consumer propagation, open-world parsing, misleading green tests, cold-session resume, coordinated rollout surfaces and instruction precedence.
- Full harness proof: 19/19 structures complete; every flawed starter passes its public tests and is rejected by the hidden grader; every reference solution passes public and hidden checks. The six-family battery additionally rejects 12 public-green negative controls at scores from 25 to 85 while all six references score 100.
- Experiment lifecycle: randomized staged 40-run plan, explicit per-stage approval, exclusive campaign/provider locks, orphan refusal, host grading, cost ceilings and retained invalid-attempt evidence are implemented.
- Complex screen execution: exactly 6/6 approved Codex calls completed sequentially with zero orphans, overlaps, invalid outcomes, Claude calls or protected-file changes. Both arms scored 95/100 in all three pairs, so the predeclared conclusion is `NO_ACTIONABLE_SIGNAL`.
- **Verification loop (release 0.4.0), measured on a real shipped fix**: on a shadow-replay of the NYRx parser rework, the lean loop scored **100/100/100** — matching the fix a human engineer actually shipped — against an unscaffolded control's **77/77/77**, three trials per arm. Guided feedback alone (failing checks handed back with their conventions) took the bare agent to 100 at 2–4× tokens; the lean scaffold path cost 5–9×. Full narrative, including the campaigns we invalidated, in [`Setup/benchmarking/verification-loop-results.md`](Setup/benchmarking/verification-loop-results.md).
- **Prompt scaffolding measured as overhead and removed**: across six fixtures and 17 calls the unscaffolded arm matched or beat every scaffolded arm at 4–10.7× the cost. The five-level mode ladder, the impact-map form and the adversarial-threat-model form are gone; what replaced them is a check suite the harness executes and the agent cannot weaken.
- **Benchmark protocol hardened by its own failures**: verdicts require ≥3 trials per arm (the same arm swung 73→89 on identical inputs); fixtures pass an admission gate before they cost money; a canary call validates a fixture before a main stage; checks live harness-side, because a campaign whose control could read the checks measured the checks, not the loop (11 calls, discarded).
- Complex screen resource evidence: at tied measured quality, Core+Router+enforcement used 253.1 versus 216.5 median wall seconds (+16.9%) and 262,510 versus 215,413 median observed tokens (+21.9%). Subscription monetary cost was not exposed and was not estimated.

## Current benchmark state

- Nineteen private fixtures are executable and validated; `REQ-EVAL-002` remains verified with stronger multi-task isolation evidence.
- Dedicated `AgenticBench` WSL isolation is verified: C: is not mounted, Windows interop and sudo are absent, the provider user has no privileged groups, and central hidden graders remain host-only.
- Codex CLI 0.144.3 and Claude Code 2.1.207 are installed user-locally in the dedicated distro; versions are discovered dynamically and may change on an explicit tools refresh.
- Both one-time OAuth logins inside `AgenticBench` are complete. Doctor and benchmark preflight pass; normal reboots do not require setup or login again.
- The first provider-backed smoke is preserved as a closed, non-publishable infrastructure shakeout. It exposed concurrent-runner and enforcement defects; no result from that campaign may be used as a Codex/Claude or vanilla/full comparison.
- The repaired four-call smoke completed cleanly: exactly four sequential calls, all public/hidden scores 100, zero overlaps and zero invalid attempts. This proves harness viability, not full-arm lift; n=1 per cell is inconclusive and Codex's exact provider-default model remains unresolved.
- Future runs no longer use an anonymous default. The current ignored, weekly-expiring local snapshot explicitly selects `gpt-5.6-sol` at medium effort and `claude-opus-4-8` at medium effort; this does not rewrite historical smoke telemetry, Stable rules or user defaults.
- The non-publishable minimum-cost calibration completed exactly two Codex calls on `database-migration-rollback`: vanilla and Core+Router+enforcement both scored 100/100. There were zero overlaps, invalid attempts, replacements or Claude calls. The predeclared ceiling rule stopped all further spend; a harder fixture must be validated before any new provider approval.
- The full release gate currently passes 17/18 checks. Its only red check is intentional: 24 objective requirements still need evidence, so the repository must not claim completion yet. Infrastructure alone passes 14/14.
- Campaign `20260713-181006-complex-ingestion-screen` is complete and permanently stopped at screening. Exactly six paired Codex calls produced identical 95/100 scores and no critical-floor difference. The only shared failure was `replay-duplicate`: all six solutions added `index` to a skipped duplicate while the hidden grader required exact equality without it, exposing a public-contract/hidden-grader alignment concern. The immutable report is under `Evals/reports/20260713-181006-complex-ingestion-screen-complex-screen.{json,md,pdf}`.
- The independent six-family battery passes 19/19 full-harness validation. Its 12 negative controls all pass public tests and are rejected by hidden graders; its six reference solutions score 100. The three-page Setup guide passed visual and PDF integrity QA.
- Campaign `20260713-201400-real-world-battery-screen` is prepared with 12 unique Codex cells, staged as separately approved 6 + 6 calls on six task families and two arms. It has zero approvals, zero run IDs, 13 current harness hashes and explicit `gpt-5.6-sol`/medium. No provider call, replication, Claude stage or automatic promotion is authorized.
- A real weekly research candidate has not yet completed.
- Automatic model switching remains disabled until staged A/B evidence covers quality, cost and latency.

No commit or push has been performed.

## Safe subscription benchmarks

Provider-backed benchmarks run in a separate WSL2 distribution named `AgenticBench`. It has no mounted Windows drive, no Windows executable interop, no `sudo`, no personal files and no hidden graders. Only a public run workspace is copied in; the returned workspace is size/type/secret checked before host-only grading.

One-time setup on a fresh clone:

```powershell
powershell -ExecutionPolicy Bypass -File Setup/benchmark.ps1 -Create -LoginCodex -LoginClaude -RefreshProviderCatalog
```

OAuth stays inside the local WSL distribution. Git ignores machine-local settings and known provider credential paths; the infrastructure gate also scans candidate repository files for credential-shaped content.

Create and run only the four-run smoke stage first:

```powershell
powershell -ExecutionPolicy Bypass -File Evals/tools/new-benchmark-campaign.ps1
powershell -ExecutionPolicy Bypass -File Evals/tools/approve-benchmark-stage.ps1 -Campaign <id> -Stage smoke -ApprovedBy <name>
powershell -ExecutionPolicy Bypass -File Evals/tools/run-benchmark-stage.ps1 -Campaign <id> -Stage smoke -MaxRunsThisInvocation 4
```

The remaining gates add 4, 16 and 16 runs, reaching cumulative totals of 8, 24 and 40. Each stage needs separate approval. Creating `Evals/local/STOP` stops the loop before the next run. Every post-smoke stage rejects volatile `provider-default` selectors and requires a fresh explicit model snapshot.

After a universal smoke ceiling, create the screening-only two-call calibration instead of unlocking a larger stage:

```powershell
powershell -ExecutionPolicy Bypass -File Evals/tools/new-benchmark-calibration.ps1
powershell -ExecutionPolicy Bypass -File Evals/tools/approve-benchmark-stage.ps1 -Campaign <id> -Stage calibration -ApprovedBy <name>
powershell -ExecutionPolicy Bypass -File Evals/tools/run-benchmark-stage.ps1 -Campaign <id> -Stage calibration -MaxRunsThisInvocation 2
```

Creation costs zero calls. Approval and execution are separate; never combine them in automation. The calibration is excluded from publishable confirmatory scores and cannot authorize follow-up runs.

The validated composite screen is documented in [`Setup/benchmarking/complex-benchmark-design.md`](Setup/benchmarking/complex-benchmark-design.md) and its matching PDF. Its first stage requires a separate approval for exactly six calls:

```powershell
powershell -ExecutionPolicy Bypass -File Evals/tools/approve-benchmark-stage.ps1 -Campaign 20260713-181006-complex-ingestion-screen -Stage complex-screen -ApprovedBy <name>
powershell -ExecutionPolicy Bypass -File Evals/tools/run-benchmark-stage.ps1 -Campaign 20260713-181006-complex-ingestion-screen -Stage complex-screen -MaxRunsThisInvocation 6
```
