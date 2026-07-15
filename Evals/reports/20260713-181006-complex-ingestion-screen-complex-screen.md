# Complex Benchmark Screen Report

- Campaign: `20260713-181006-complex-ingestion-screen`
- Generated: 2026-07-13T19:17:19.2665153+02:00
- Measurement integrity: **PASS**
- Comparative conclusion: **NO_ACTIONABLE_SIGNAL**
- Claim level: screening only; not publishable evidence

## Executive result

Exactly six approved Codex calls completed sequentially with no orphan, Claude, overlapping or invalid execution. Vanilla and Core + Router + enforcement both scored 95/100 in all three paired trials. Every paired quality delta was zero and no critical floor differed, so the predeclared decision is NO_ACTIONABLE_SIGNAL. No confirmation or cross-provider call is authorized.

The full environment used more resources without a measured quality gain in this screen: median wall time was 253.1 versus 216.5 seconds (+16.9%), and median observed tokens were 262510 versus 215413 (+21.9%). Subscription monetary cost was not reported by the CLI and is not estimated.

## Paired outcomes

| Trial | Seed | Vanilla | Full | Quality delta | Vanilla sec | Full sec | Vanilla tokens | Full tokens |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 20260714 | 95 | 95 | 0 | 214.4 | 253.1 | 236350 | 262510 |
| 2 | 20260715 | 95 | 95 | 0 | 216.5 | 202.1 | 215413 | 253000 |
| 3 | 20260716 | 95 | 95 | 0 | 229.3 | 262.4 | 199383 | 267576 |

## Absolute quality by arm

| Arm | Quality median | Functional | Generalization | Reliability | Security | Edge cases | Performance |
|---|---:|---:|---:|---:|---:|---:|---:|
| Vanilla | 95 | 20/20 | 25/25 | 15/20 | 15/15 | 10/10 | 10/10 |
| Core + Router + enforcement | 95 | 20/20 | 25/25 | 15/20 | 15/15 | 10/10 | 10/10 |

## Fixture-alignment finding

**Review required.** All six runs failed only `replay-duplicate`. Each solution returned a duplicate record with `provider`, `id`, `reason` and `index`; the hidden check required exact equality without `index`. The task explicitly fixes the fields of rejected records, but does not state an equally explicit exact-field schema for skipped records.

This common-mode result is evidence that the fixture needs clarification. The original pinned outcomes remain immutable. A future version should define the skipped schema explicitly, add a public contract assertion, rerun deterministic controls and receive fresh approval before any provider calls.

## Integrity and cost evidence

- Approved and completed calls: 6/6.
- Orphans / Claude calls / overlaps / invalid outcomes: 0 / 0 / 0 / 0.
- Protected benchmark-file changes: 0.
- Total observed tokens: 1434232.
- Provider-reported monetary-cost coverage: 0/6 provider calls; basis: not-reported-by-subscription-cli.

## Decision and next gate

**STOP.** Do not run confirmation, Claude, directional, confidence or pilot stages from this result. Clarify the fixture contract, strengthen its public/hidden alignment, revalidate the discrimination ladder without provider calls, and only then propose a fresh bounded screen for explicit human approval.

## Required fixture repair

- Define the exact `skipped` record schema in the public task and assert it in a public contract test.
- Keep the original campaign and pinned grader immutable; version the repaired fixture instead of rewriting history.
- Re-run starter, all negative controls and the reference solution locally before any provider approval.
- Add more than one difficult task family so a single shared interpretation cannot dominate the comparison.
- Preserve paired seeds, sequential execution, zero automatic replacements and explicit per-stage approval.

## Interpretation limits

- Three trials per arm support screening decisions only; they do not establish statistical significance.
- This evidence covers one Codex model, one effort level and one composite Python fixture.
- Token counts are observable resource use; subscription monetary charges are not exposed by the CLI.
- Identical scores do not prove the environment has no value; they prove this screen measured no lift.

The structured JSON beside this report is the measurement source of truth. This PDF is the human-readable rendering.
