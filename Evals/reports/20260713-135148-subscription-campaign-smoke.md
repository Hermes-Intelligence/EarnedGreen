# Smoke Benchmark Report

- Campaign: `20260713-135148-subscription-campaign`
- Generated: 2026-07-13T14:22:20.2961160+02:00
- Verdict: **PASS**
- Comparative conclusion: **INCONCLUSIVE**

## Executive result

All 4/4 approved calls passed public tests, hidden grading at 100/100 and applicable enforcement. There were 0 overlapping executions and 0 invalid attempts. This proves smoke viability of the repaired harness; it does not prove that the full arm outperforms vanilla.

## Run evidence

| Provider | Arm | Model evidence | Seconds | Public | Hidden | Enforcement | Protected changes |
|---|---|---|---:|---|---:|---|---:|
| claude | core-router-enforcement | claude-opus-4-8 (provider-event) | 90.1 | True | 100 | True | 0 |
| codex | vanilla | unresolved-provider-default (not-reported) | 59 | True | 100 | True | 1 |
| codex | core-router-enforcement | unresolved-provider-default (not-reported) | 93.3 | True | 100 | True | 0 |
| claude | vanilla | claude-opus-4-8 (provider-event) | 69.3 | True | 100 | True | 0 |

## Integrity and review

- Harness snapshot: 5 pinned file hashes.
- Full-arm protected-input integrity: True.
- Total provider wall time: 311.7 seconds.
- Immediately after stage completion, all five pinned harness hashes matched and exactly four provider executions existed since campaign creation.
- Codex vanilla added useful regression cases inside the existing public test file; it did not delete or weaken assertions, but this is reported as a protected-input change that the full arm avoided by creating a separate regression file.

## Publication blockers

- Only one trial per provider/arm cell; comparative effect is statistically inconclusive.
- Codex provider-default did not report an exact resolved model; post-smoke stages require explicit model selectors.

## Next gate

Directional remains unapproved. Create a new campaign with explicit model selectors before any post-smoke calls, then require separate human approval.

Structured JSON beside this report is the measurement source of truth. The PDF is a human-readable artifact.
