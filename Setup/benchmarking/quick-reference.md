## Benchmarking Quick Reference

1. Pass infrastructure and `AgenticBench` doctor gates.
2. Confirm both subscription logins and a provider snapshot younger than seven days.
3. Create the campaign without starting a model.
4. Approve only the next stage: smoke, directional, confidence or pilot.
5. Use one terminal and one runner only; never start a second runner to recover a silent window.
6. Execute only inside the copied public workspace.
7. Grade public behavior and the hidden case on the host after agent exit.
8. Stop on `Evals/local/STOP`, timeout, auth drift, isolation drift, orphan process or two consecutive failures.
9. Complete five trials per fixture/provider/arm cell only after earlier gates justify the spend.
10. Summarize uncertainty and promote rules separately with human approval and rollback.

Pilot: `2 fixtures x 2 providers x 2 arms x 5 trials = 40 runs`.

Spend ladder: `4 -> 8 -> 24 -> 40` cumulative runs. Start with four, not forty.

Hold fixed: resolved model, effort, prompt, fixture, permissions, budgets, grader and environment.

Never claim that routing equals coding quality, public tests equal final-state proof, logical separation equals hidden isolation, an alias equals the resolved model, SWE-bench Verified is the primary 2026 frontier metric, or a benchmark score automatically measures human productivity.

Smoke may use `provider-default`; every later stage requires explicit models. Publication requires complete cells, inaccessible grader, resolved model telemetry, approved stage budgets, no concurrency, no leakage, retained failures and reported uncertainty.

### Fixture admission (pre-spend)

Hard requirement, enforced by the campaign creation tools and `approve-benchmark-stage.ps1`. No paid campaign is constructed and no stage is approved unless every fixture scheduled in it holds a fresh validity record: an `Evals/reports/*-outcome-harness.json` result for that fixture with `passed=true` whose `run_at` is newer than the fixture's newest file write. A fixture without such a record is refused by name with the exact command to produce one. Revalidating a single fixture is cheap:

```powershell
powershell -ExecutionPolicy Bypass -File Evals/validate-outcome-harness.ps1 -Fixture <fixture-id>
```

### Canary rule

Hard requirement, planned by the campaign creation tools and enforced by `run-benchmark-stage.ps1`. Any fixture with zero prior paid runs whose run-record shows `outcome_valid=true` is a canary: its plan runs carry `canary=true`, its first stage executes at most one run, and every later-stage run for that fixture is refused until the canary run-record exists with `outcome_valid=true` and at least two distinct grader check dimensions. A grader that collapses to a single dimension therefore blocks all further spend on that fixture instead of silently invalidating a full campaign.

Note: `quick-reference.pdf` predates the two sections above; regeneration with `build-pdfs.py` is pending (the renderer's `reportlab` dependency is not installed on this host). Markdown is the source of truth.
