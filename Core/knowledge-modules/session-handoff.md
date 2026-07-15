# Session Handoff

Persist only high-signal state:

- objective and active requirement IDs,
- completed changes,
- decisions and rejected approaches,
- evidence and failed checks,
- blockers and unresolved risks,
- exactly one next action.

Do not store private chain-of-thought. Raw transcripts are diagnostic artifacts, not primary project memory. Use event-driven checkpoints at meaningful state changes rather than logging every tool call into the repository.
