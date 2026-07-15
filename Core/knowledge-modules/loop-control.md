# Loop Control

Before starting an autonomous loop, create a loop manifest containing:

- objective and immutable non-goals,
- measurable completion check,
- progress signal,
- maximum turns, time and cost where available,
- repeated-failure and no-progress limits,
- kill switch,
- allowed actions and isolation boundary,
- escalation conditions,
- checkpoint and evidence paths.

The generator does not grade its own subjective work for high-risk tasks. Use deterministic graders first and an independent fresh-context evaluator where judgment is required. Stop on completion, budget, no progress, repeated failure, required new authority or unsafe uncertainty.
