# Adaptive-layer boundary fixtures

These fixtures were authored and admission-gated inside the candidate package
`Research/candidate-packages/2026-07-14-adaptive-agent-modes-v2` and are
promoted here for durability. They are deliberately NOT registered in
`Evals/fixtures/catalog.json`:

- The stable outcome harness (`Evals/validate-outcome-harness.ps1`) iterates
  only the catalog, so these directories are inert for the stable
  fixture-discrimination gate. Their contract shape (dual references,
  `hidden/reference-format-alt/`, banded negative controls such as
  `plausible-cold-pass`, `fixture-contract.json` with `decision_points` /
  `serialized_output_dimensions` / `process_ground_truth`) is richer than the
  catalog contract and is graded by the ADAPTIVE harness instead.
- Grading and admission run through the candidate tooling (or its promoted
  copies): `awbp/fixture_admission.py --fixture <dir>` validates a
  fixture fail-closed before any paid run; campaign tooling remains
  candidate-side until promoted separately.

| Directory | Fixture id | Class |
| --- | --- | --- |
| `adaptive-contract-evolution-v2/` | adaptive-contract-evolution-v2 | mode-boundary |
| `adaptive-contract-evolution-v3/` | adaptive-contract-evolution-v3 | mode-boundary |
| `adaptive-contract-evolution-v4/` | adaptive-contract-evolution-v4 | mode-boundary (semantic serialization grading) |
| `implicit-conventions-v1/` | implicit-conventions-v1 | underspecified-by-design (clarity axis) |
| `implicit-conventions-scale-v1/` | implicit-conventions-scale-v1 | underspecified-by-design (scale axis) |

Registering any of these in the stable catalog requires adapting it to the
catalog contract first and re-running the fixture-discrimination gate.
