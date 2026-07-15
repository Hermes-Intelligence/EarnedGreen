# Real-World Battery Sentinel Report

- Campaign: `20260713-201400-real-world-battery-screen`
- Generated: 2026-07-13T21:53:44.2760578+02:00
- Measurement integrity: **PASS**
- Comparative conclusion: **NO_ACTIONABLE_SIGNAL**
- Claim level: cost-bounded screening only

## Executive result

Exactly six approved Codex calls completed sequentially across three production-style task families. Every vanilla/full pair received the same hidden score and had the same critical-check outcome. The predeclared sentinel result is therefore NO_ACTIONABLE_SIGNAL: this stage measured no quality improvement from Core + Router + enforcement.

Median wall time was 148.1 seconds for full versus 118.3 for vanilla (+25.2%). Median observed tokens were 189758 versus 138906 (+36.6%). The subscription CLI did not report monetary cost, so no dollar estimate is invented.

## Task outcomes

| Task family | Vanilla | Full | Delta | Vanilla issue | Full issue |
|---|---:|---:|---:|---|---|
| api-contract-propagation | 90 | 90 | 0 | input-validation | input-validation |
| coordinated-release-change | 90 | 90 | 0 | documentation | documentation |
| resumable-batch-session | 100 | 100 | 0 | none | none |

## Resource comparison

| Arm | Median score | Mean score | Quality passes | Median seconds | Median tokens |
|---|---:|---:|---:|---:|---:|
| Vanilla | 90 | 93.33 | 1/3 | 118.3 | 138906 |
| Core + Router + enforcement | 90 | 93.33 | 1/3 | 148.1 | 189758 |

Full used more time and tokens without a measured quality gain in this sentinel. This is evidence against assuming that more context automatically helps; it is not proof that the full environment has no value on the three untested diversity families.

## What the failures reveal

- API propagation: both arms reached 90/100 and missed input validation. Both updated hidden consumers, so the fixture successfully exposed a narrower contract-quality gap.
- Coordinated release: both arms reached 90/100 and missed the documentation check. Code, migration and observability behavior passed, but neither completed the full product change.
- Resumable session: both arms reached 100/100, including split resume, failure recovery, corruption handling and schema safety.

## Integrity evidence

- Approved/completed calls: 6/6; unique run IDs: 6.
- Provider executions / orphans / overlaps / invalid outcomes: 6 / 0 / 0 / 0.
- Protected-file changes: 0; later-stage run IDs: 0.
- Total observed tokens: 976301; provider-reported USD coverage: 0/6.

## Decision and next gate

**STOP at the approval boundary.** The sentinel is complete, and the campaign is waiting for a separate decision on the six-call diversity stage. No diversity, replication, Claude, Stable promotion or automatic model switching is authorized by this result.

If diversity is approved, it should be justified as testing three materially different failure families - open-world parsing, misleading-green cache behavior and instruction-precedence defense - not as a retry of this tie. The complete six-family screen would still be exploratory and non-confirmatory.

The structured JSON beside this report is the measurement source of truth. The PDF is the human-readable rendering.
