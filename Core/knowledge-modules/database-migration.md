# Database Migration Safety

- Classify compatibility and data-loss risk before editing.
- Prefer expand/migrate/contract for live systems.
- Define rollback or forward-recovery behavior.
- Test old and new application versions where staged rollout matters.
- Validate backfills for idempotency, resumability, batching and observability.
- Check constraints, indexes, locks and production-scale execution cost.
- Never infer production data shape only from local fixtures.
