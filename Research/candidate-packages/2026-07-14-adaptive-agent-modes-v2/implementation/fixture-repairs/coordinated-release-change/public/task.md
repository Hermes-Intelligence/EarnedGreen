# Task: coordinate an expand-migrate-contract schema rollout (v2)

Move the user schema from legacy field `email` to `primary_email` across runtime code, serialization, migration, documentation and observability.

## Runtime contract

- `model.normalize_user(record)` accepts legacy-only, current-only or equal dual-field records.
- `id` and the selected email are non-blank strings; conflicts raise `ValueError`.
- Return exactly `{"id": string, "primary_email": string}` without mutation.
- `api.serialize_user(record, include_legacy=True)` also returns matching `email`.

## Backfill contract

- Deep-copy the list, process only the requested slice and retain legacy `email` during expand.
- Current/equal rows remain unchanged; conflicts are retained and counted.
- Return exactly `rows`, `next_cursor` and metrics; repeated runs are resumable and idempotent.
- Invalid cursor and limit values raise `ValueError`.

## Operations contract

- Track `legacy_reads`, `current_reads`, `conflicts` and `backfilled`.
- Update `docs/user-schema.md` with semantic guidance for expand, migrate, contract and rollback. It must communicate that legacy email remains retained during expand, but no specific verbatim sentence or Markdown formatting is required.
- Preserve public imports and do not modify `task.md` or existing public tests.
