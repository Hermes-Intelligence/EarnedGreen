# Calibration Benchmark Report

- Campaign: `20260713-151556-calibration-probe`
- Generated: 2026-07-13T16:00:02.1886024+02:00
- Verdict: **PASS**
- Comparative conclusion: **CEILING**

## Executive result

All 2/2 approved calls passed public tests, hidden grading at 100/100 and applicable enforcement. There were 0 overlapping executions and 0 invalid attempts. Both arms reached the ceiling, so this fixture cannot discriminate between vanilla and the full environment. The predeclared decision is STOP: spend zero Claude calls and redesign a harder fixture.

## Run evidence

| Provider | Arm | Model evidence | Seconds | Public | Hidden | Enforcement | Protected changes |
|---|---|---|---:|---|---:|---|---:|
| codex | vanilla | gpt-5.6-sol (explicit-cli-selector) | 77.5 | True | 100 | True | 0 |
| codex | core-router-enforcement | gpt-5.6-sol (explicit-cli-selector) | 138.7 | True | 100 | True | 0 |

## Integrity and review

- Harness snapshot: 5 pinned file hashes.
- Full-arm protected-input integrity: True.
- Total provider wall time: 216.2 seconds.
- Both implementations changed only src/migration.py and are semantically equivalent: schema introspection, idempotent upgrade, reversible downgrade, row and UNIQUE preservation. Vanilla provider wall time was 77.5 seconds; full-arm provider wall time was 138.7 seconds; this two-call screening probe is not a latency estimate.

## Publication blockers

- Screening-only calibration is excluded from publishable confirmatory scores.

## Next gate

STOP: both arms scored 100. Spend zero Claude calls and redesign a harder fixture before requesting any new provider approval.

Structured JSON beside this report is the measurement source of truth. The PDF is a human-readable artifact.
