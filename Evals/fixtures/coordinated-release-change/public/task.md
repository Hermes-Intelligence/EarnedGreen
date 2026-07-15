# Task: coordinate an expand-migrate-contract schema rollout

The user schema is moving from legacy field `email` to `primary_email`. Implement the expand phase across runtime code, serialization, migration, documentation and observability.

## Runtime contract

- `model.normalize_user(record)` accepts legacy-only, current-only or both fields when their values agree.
- `id` and the selected email must be non-empty strings.
- Conflicting `email` and `primary_email` values raise `ValueError`.
- Return exactly `{"id": string, "primary_email": string}` without mutating input.
- `api.serialize_user(record, include_legacy=False)` returns that current shape. With `include_legacy=True`, return exactly `id`, `primary_email` and matching `email`.

## Backfill contract

Implement `migrations.backfill_primary_email.backfill(rows, start=0, limit=None)`:

- Deep-copy the whole list and process only the requested slice.
- Add `primary_email` from `email` while retaining legacy `email` during the expand phase.
- Current/equal rows are unchanged; conflicting rows are retained and counted, not silently overwritten.
- Return exactly `rows`, `next_cursor` and `metrics` (`scanned`, `backfilled`, `already_current`, `conflicts`).
- `next_cursor` is the next index or `None`; repeated runs are idempotent and resumable.
- Invalid cursors/limits raise `ValueError`.

## Operations contract

- `metrics.increment`, `metrics.snapshot` and `metrics.reset` track `legacy_reads`, `current_reads`, `conflicts` and `backfilled`.
- Update `docs/user-schema.md` with explicit expand, migrate, contract and rollback guidance. It must state that legacy email is retained during expand.
- Preserve public imports and do not modify `task.md` or existing public tests.
