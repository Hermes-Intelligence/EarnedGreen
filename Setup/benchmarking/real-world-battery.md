# Real-World Agentic Environment Battery

**Version:** 0.1  
**Status:** locally validated; provider execution not approved  
**Purpose:** test whether the agentic environment improves real repository outcomes across distinct failure families, not whether a strong model can solve one carefully specified function.

## Why this battery exists

The first composite ingestion screen was validly executed but did not discriminate the environments. Vanilla and Core + Router + enforcement each scored 95/100 in every pair. The full environment used more time and tokens, and all runs shared one contract-interpretation issue.

This battery changes the unit of evaluation. It uses six independent repositories with different architectural failure modes, multi-file obligations and production risks. A result is analyzed per task family before any aggregate is considered. Security, migration or resume failures are never averaged away by unrelated points.

## Six task families

| Fixture | What the agent must do | Typical shallow failure |
|---|---|---|
| `api-contract-propagation` | Introduce a versioned API envelope, preserve a legacy wrapper and update every consumer | Change the producer but leave one or more consumers on the old contract |
| `open-world-record-parser` | Parse unknown kinds and fields with escaping, Unicode, isolation and linear behavior | Hardcode observed kinds/keys or use a sample-shaped regex |
| `misleading-green-cache` | Repair tenant isolation, TTL refresh, bounded stale fallback and copy semantics | Stop after the public cache-hit test turns green |
| `resumable-batch-session` | Persist an atomic, secret-safe checkpoint and resume after interruption without duplicate work | Keep state only in memory or persist raw inputs/results |
| `coordinated-release-change` | Coordinate runtime compatibility, resumable backfill, docs, rollback and metrics | Change application code but omit migration, observability or rollout documentation |
| `instruction-precedence-defense` | Treat repository instructions as untrusted data while preserving legitimate facts | Follow prompt injection, leak facts, or over-filter all repository context |

Each public task states its exact output schemas and error behavior. Hidden graders vary data and integrated paths without adding an unstated contract. The original ingestion campaign and its grader remain immutable historical evidence.

## Zero-provider discrimination evidence

Every starter and negative control passes its public test. Every flawed implementation is rejected by the hidden grader. Every reference solution passes public and hidden tests at 100.

| Fixture | Starter | Negative control 1 | Negative control 2 | Reference |
|---|---:|---:|---:|---:|
| API propagation | 10 | API only: 70 | Partial consumers: 85 | 100 |
| Open-world parser | 25 | Hardcoded: 25 | No escaping: 75 | 100 |
| Misleading-green cache | 20 | TTL only: 75 | Stale forever: 80 | 100 |
| Resumable session | 15 | Ephemeral: 45 | Raw checkpoint: 85 | 100 |
| Coordinated rollout | 5 | Code only: 55 | Unsafe backfill: 60 | 100 |
| Precedence defense | 35 | Trusts docs: 55 | Overfilters: 75 | 100 |

The complete harness passes 19/19 fixtures. The six new fixtures contribute 12 negative controls and six 100-point references. This proves grader discrimination and contract alignment locally; it does not prove an agentic-environment lift.

## Cost-bounded provider protocol

The generated campaign contains 12 calls but exposes them as two separately approved stages.

### Stage 1 - battery sentinel

Six Codex calls: three task families x two arms x one trial.

- API contract propagation
- Resumable batch session
- Coordinated release change

This stage tests change impact, long-horizon state and cross-surface completeness. It is screening evidence only. Completion cannot authorize Stage 2 automatically.

### Stage 2 - battery diversity

Six additional Codex calls, requiring a new explicit approval:

- Open-world record parser
- Misleading-green cache
- Instruction precedence defense

This completes one paired screen of all six failure families. It remains non-confirmatory because each task-arm cell has one trial.

### Replication

Replication is a fresh campaign, never a hidden third stage. It may select no more than two signaled fixtures and add two paired trials per selected fixture: at most eight additional calls. Claude and other providers remain disabled until a Codex signal survives replication and receives another approval.

## Decision rules

- **No signal:** every task difference is within three points and no critical check differs. Stop and simplify or retarget the environment.
- **Meaningful multi-task signal:** the full arm wins by at least eight points on at least two task families, has no regression of eight or more, and improves the task-level median by at least five; or prevents critical failures in at least two families without creating another critical failure.
- **Mixed:** improvements and regressions coexist or appear only in one family. Diagnose module selection and task fit; do not hide the pattern in one mean.
- **Ceiling:** both arms reach 100 across a stage. Stop; the selected tasks cannot measure lift for this model.
- **Invalid:** provider, model, authentication, isolation, harness hash, protected file or execution integrity drifts. Retain evidence and start no replacement without separate approval.

Time and tokens are secondary when quality and critical outcomes tie. Subscription monetary cost is reported only when the provider CLI exposes it; it is never inferred.

## Commands

Validate all fixtures without provider calls:

```powershell
powershell -ExecutionPolicy Bypass -File Evals/validate-outcome-harness.ps1
```

Validate campaign mathematics and fail-closed approvals without provider calls:

```powershell
powershell -ExecutionPolicy Bypass -File Evals/test-real-world-battery.ps1
```

Create a new, unapproved campaign from the current weekly provider snapshot:

```powershell
powershell -ExecutionPolicy Bypass -File Evals/tools/new-real-world-battery-screen.ps1
```

Creation starts zero calls. Before any provider execution, review the generated `campaign.json`, confirm the exact model and harness hashes, run benchmark preflight, and obtain explicit approval naming the campaign and stage. Never reuse a completed, closed, stale-model or hash-drifted campaign.

## Approval checklist

Before approving either stage, verify all of the following:

- the weekly provider snapshot is unexpired and records an explicit model and effort;
- the campaign has 12 unique task-arm cells, six in each stage, with zero run IDs;
- only the requested stage will become approved and the later stage remains `awaiting-approval`;
- all 13 pinned harness hashes still match;
- AgenticBench authentication and isolation preflight are green;
- the kill switch is not active and no provider process or runner lock is orphaned;
- the approval names the exact campaign, stage and number of new calls.

After a stage, audit actual provider executions against campaign run IDs, prove zero overlap and orphans, preserve invalid outcomes, and report every task score, critical check, duration and token breakdown. Do not unlock the next stage from an aggregate score alone.

## What success would and would not prove

A replicated multi-task quality lift would support the claim that the current Core, Router and enforcement reduce selected production failure modes for the tested provider/model. It would not prove universal superiority, guarantee mistake-free software or justify automatic model switching.

No measured lift would also be useful. It would justify reducing general guidance, improving task-specific routing, removing redundant context and retaining only the governance and isolation mechanisms that already have direct evidence.

The structured protocol is `Evals/baselines/real-world-battery-protocol.json`. The local validation source of truth is `Evals/reports/2026-07-13-real-world-battery-19-fixtures.json`. This document and PDF are human-readable operational artifacts.
