# Complex Production Benchmark Design

## What this benchmark measures

`production-ingestion-evolution` is a small production repository rather than a one-function puzzle. The required output contract is exact, but the implementation architecture is open. The agent must evolve a provider-driven ingestion pipeline while preserving compatibility and handling state, untrusted data, unknown future providers, malformed siblings and thousands of records.

The hidden score is 100 points across six independent dimensions:

| Dimension | Points | Representative failures |
|---|---:|---|
| Functional behavior | 20 | alternate layouts, ordering, downstream summary compatibility |
| Generalization | 25 | hardcoded providers/entities, unseen runtime specs, Unicode and metamorphic renaming |
| Reliability | 20 | replay idempotency, identity conflicts, JSON/legacy state, mutation and failure isolation |
| Security | 15 | recursive secret leakage, prompt-like text handling and safe rejection records |
| Edge cases | 10 | empty batches, zero timestamps, invalid adapters and malformed values |
| Performance | 10 | a 5,000-record batch under a fixed local budget |

Names used by generalization checks vary deterministically by paired trial seed. Both arms receive the same seed, while separate trials receive different unseen names. Hidden material and seeds remain host-side.

## Proof that the grader discriminates

Before spending a provider call, five implementations were evaluated:

| Implementation | Hidden score | Intended defect class |
|---|---:|---|
| Public starter | 46 | sample-driven, stateless and unsafe |
| Hardcoded negative control | 46 | more examples encoded as a closed allowlist |
| Secure but closed | 70 | reasonable state/security, but fixed provider/entity universe |
| Generic but stateless | 85 | general and safe, but broken replay/conflict/legacy-state behavior |
| Reference | 100 | complete outcome contract |

Every implementation passes the public happy path. This establishes a 54-point range and a 15-point margin between the strongest negative control and the reference. It does not guarantee that two frontier-model arms will differ; it demonstrates that the task and grader can reveal materially different solution quality.

## Comparing quality, time and cost

Quality is primary. Report the total score and all six dimensions. A quality difference is operationally meaningful at eight points, or when one arm clears a critical generalization, reliability or security floor that the other misses.

For every call record:

- provider wall-clock seconds;
- input, cached/cache-created, output and reasoning tokens when exposed;
- total observed tokens using provider-specific accounting semantics;
- provider-reported USD cost when available;
- an explicit `not-reported-by-subscription-cli` marker otherwise.

Provider-reported USD is not presented as the user's subscription charge. Time or resource use breaks a tie only when absolute quality is equivalent and critical outcomes match. Never combine a security failure and lower cost into one flattering efficiency score.

## Cost-bounded experiment ladder

1. `complex-screen`: three paired Codex trials per arm, six calls total. This is screening evidence, not a significance claim.
2. Stop on a repeated ceiling, no actionable paired difference, or infrastructure invalidity.
3. `complex-confirm`: only after a material signal and separate approval, add two paired trials per arm for five per arm and ten Codex calls cumulative.
4. `cross-provider`: Claude remains disabled unless the Codex effect survives confirmation; it requires another approval.

No stage unlocks automatically. A clean workspace, exact model selector, fixed effort, paired grader seed, identical limits and randomized arm order are mandatory.
