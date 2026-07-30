# Verification Loop

Your work is verified by an independent check suite (`.agentic/check-suite.json`), not by your own claims. The suite is frozen: harness-authored checks and the loop budgets carry a digest, and weakening, removing or reconfiguring them fails the gate. You may add checks; you may never subtract.

The loop: implement, then run one iteration —

```
python .agentic/verification_loop.py step --suite .agentic/check-suite.json --workspace .
```

Exit 0 means every independent check passes: proceed to the pre-submit gate. Exit 1 means failures remain: read `.agentic/loop-feedback.json`, fix the listed failures at their cause, and run the step again. Exit 2 means the loop terminated (iteration budget or no progress): stop mutating, checkpoint, and escalate to the owner with the remaining structured failures — do not try to exit the loop by editing checks.

Check kinds you will meet:

- **acceptance** — a command that must exit 0 (frozen spec acceptance tests, public tests).
- **differential** — the same command runs on the pre-change baseline and on your workspace; every output difference must be covered by the declared expected changes. An unexpected diff is a silent regression: restore the behavior or, if the change is genuinely required by the task, say so to the owner — never widen the expectations yourself.
- **symbol-sweep** — every file referencing a symbol you touched must be either changed by you or recorded in `.agentic/evidence.json` under `consumer_inspections` as `{"path": ..., "note": <what you verified>}` after you actually read it. An empty note does not count.
- **property** — an invariant over real data samples. If it fails, the requirement it encodes is real even if the task text never mentioned it: data is part of the spec.
- **finding** — an independent-verifier finding. It stays failing until `.agentic/finding-resolutions.json` names a command that proves the fix (re-executed by the harness) or records an explicit owner waiver. Prose never resolves a finding.

The gate re-runs this entire suite itself at completion. A green loop report you wrote is not evidence; only the re-execution is.
