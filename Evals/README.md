# Evaluation Harness

The suite has two layers:

1. **Deterministic infrastructure tests** validate objective coverage, routing, source governance, stable-path immutability and PDF links.
2. **Agent outcome trials** compare vanilla, Core, Core+Router and Core+Router+enforcement on isolated fixtures with hidden graders.

`cases.json` defines the routing cases. `fixtures/catalog.json` contains 19 executable outcome fixtures. `baselines/arms.json` fixes experimental controls and metrics. Run the deterministic routing suite with:

```powershell
powershell -ExecutionPolicy Bypass -File Evals/run-evals.ps1 -Mode routing
```

Agent outcome results must include exact provider surface, model/version, reasoning effort, permissions, run budget, trial seed/ID and artifact hashes. Do not publish a baseline score until at least five trials per case and arm complete. Hidden graders must live outside the agent's writable/readable fixture.

The initial repository contains the protocol and routing graders. Provider adapters and executable hidden fixtures are promoted separately after their isolation has been verified; until then objective `REQ-EVAL-001/002` remains incomplete.

## Executable fixtures

All 19 catalog fixtures are executable. Validate their negative controls, public tests, hidden graders and reference solutions with:

```powershell
powershell -ExecutionPolicy Bypass -File Evals/validate-outcome-harness.ps1
powershell -ExecutionPolicy Bypass -File Evals/test-run-lifecycle.ps1
```

For subscription-backed Codex and Claude comparisons, use `new-benchmark-campaign.ps1`, `approve-benchmark-stage.ps1` and `run-benchmark-stage.ps1`. The campaign is staged 4 -> 8 -> 24 -> 40 and uses `invoke-agenticbench.ps1`; it never exposes this repository or hidden graders to the provider process. Exactly one campaign runner and one provider adapter may own the fixed WSL workspace. Concurrency, orphaned provider processes and closed campaigns fail before a new provider call. The older `new-experiment.ps1` lifecycle remains a deterministic harness test and manual protocol tool.

The 2026-07-13 first smoke is diagnostic-only and `closed-diagnostic-invalid`. It records five provider invocations, including three infrastructure-invalid attempts caused by a campaign-state race. Preserve it as regression evidence; never resume or score it.

The repaired campaign `20260713-135148-subscription-campaign` completed its four-call smoke with 4/4 public passes, 4/4 hidden scores of 100, zero overlaps and zero invalid attempts. Its comparative conclusion is `INCONCLUSIVE` because every provider/arm cell has only one trial and all reached the ceiling. Structured JSON, Markdown and the visually verified PDF are under `Evals/reports/20260713-135148-subscription-campaign-smoke.*`. Directional remains unapproved.

Campaign `20260713-151556-calibration-probe` completed exactly two approved Codex calls on `database-migration-rollback`: vanilla and `core-router-enforcement`, both pinned to `gpt-5.6-sol`/medium. Both passed public tests, hidden grading at 100/100 and enforcement with zero overlaps, invalid attempts, replacements or protected-file changes. This is a screening-only CEILING result, not a publishable comparison. The predeclared rule stops all further spend, including Claude calls, until a harder fixture passes deterministic negative-control and reference validation. Structured JSON, Markdown and the visually verified PDF are under `Evals/reports/20260713-151556-calibration-probe-calibration.*`.

Local `logical-only` runs are harness tests, not publishable hidden evaluations. Publication requires container/VM or the verified dedicated `AgenticBench` WSL isolation that prevents the agent from reading this repository's `Evals/fixtures/*/hidden` paths.

## Composite production screen

`production-ingestion-evolution` is the post-ceiling benchmark. It grades functional behavior (20), generalization (25), reliability (20), security (15), edge cases (10) and performance (10). Three negative controls prove a quality ladder of 46, 70 and 85 against the 100 reference; all pass the same public test. Trial-specific unseen names are derived from a host-only paired seed.

Campaign `20260713-181006-complex-ingestion-screen` completed exactly six approved Codex runs: three vanilla and three `core-router-enforcement`, paired by trial. All executions were sequential and valid, with zero orphans, overlaps, Claude calls, replacements or protected-file changes. Every pair tied at 95/100 with no critical-floor difference, so the predeclared result is `NO_ACTIONABLE_SIGNAL`; confirmation and cross-provider stages remain unauthorized. At tied quality, the full arm used +16.9% median wall time and +21.9% median observed tokens. Subscription monetary cost was not reported and is not estimated.

All six solutions failed only `replay-duplicate` because they included `index` in the skipped record while the hidden check expected an exact object without it. Since the public task does not define that exact-field rule as explicitly as it defines rejected records, the report marks fixture alignment `REVIEW_REQUIRED`. Preserve the pinned campaign and grader; version and clarify the fixture before a fresh locally validated screen. Structured evidence and the visually verified PDF are under `Evals/reports/20260713-181006-complex-ingestion-screen-complex-screen.*`. Campaign `20260713-175734-complex-ingestion-screen` made zero calls and remains closed as superseded.

See [`Setup/benchmarking/benchmarking-handbook.md`](../Setup/benchmarking/benchmarking-handbook.md) and its PDF for the complete protocol and external benchmark ladder.

## Six-family real-world battery

The locally validated battery adds `api-contract-propagation`, `open-world-record-parser`, `misleading-green-cache`, `resumable-batch-session`, `coordinated-release-change` and `instruction-precedence-defense`. Together they contribute 12 negative controls that pass the same public tests but score between 25 and 85, while all six references score 100. The complete outcome harness passes 19/19.

`Evals/baselines/real-world-battery-protocol.json` stages provider spend at 6 + 6 calls. The first stage covers API propagation, multi-session resume and coordinated rollout. The second separately approved stage covers open-world parsing, misleading green tests and precedence defense. Replication is a fresh campaign limited to at most two signaled tasks; it never starts automatically.

Campaign `20260713-201400-real-world-battery-screen` is awaiting approval for exactly six sentinel calls. It has 12 unique scheduled cells, zero approvals, zero run IDs, zero replacements and 13 current harness hashes. Creating or approving a stage starts no provider call by itself. See [`Setup/benchmarking/real-world-battery.md`](../Setup/benchmarking/real-world-battery.md) and its visually verified PDF.
