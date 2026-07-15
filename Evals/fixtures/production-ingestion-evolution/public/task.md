# Task: evolve a production event-ingestion pipeline

Implement the public functions in `src/pipeline.py`:

```python
process_batch(records, state, adapter_specs) -> dict
summarize(events_or_batch_result) -> dict
```

The product ingests untrusted event records from an open-ended set of providers. A provider is supported by supplying a runtime adapter specification; provider names, event kinds, entity keys and values are not closed enums and must not be inferred from the examples.

## Adapter contract

`adapter_specs` maps provider names to specifications containing:

- `id_path`, `timestamp_path`, `kind_path` and `payload_path`: dot-separated paths into that provider's record;
- `entity_paths`: a mapping from canonical entity key to dot-separated record path;
- optional `kind_aliases`: a mapping from provider event kinds to canonical kinds.

Every input record has a top-level string `provider`. Paths may address nested mappings. Invalid specifications or records must be isolated as rejected records instead of aborting the batch.

## Canonical result

Return a JSON-serializable mapping with exactly these top-level sections:

- `accepted`: canonical events sorted by `(occurred_at, provider, id)`;
- `skipped`: duplicate identities with reason `duplicate`;
- `rejected`: safe records containing the input `index` and a stable `code`, without raw secrets or payload values;
- `state`: version 2 deduplication state. The returned `state` is a JSON-serializable mapping that carries its schema version under the integer key `version` set to `2` (i.e. `{"version": 2, ...}`), alongside whatever deduplication bookkeeping the implementation needs;
- `metrics`: `received`, `accepted`, `skipped` and `rejected` counts.

A canonical event contains `id`, `provider`, `kind`, `occurred_at`, `entities` and `payload`. IDs, kinds and providers are non-empty strings. Timestamps are non-negative integers. Entity values are normalized to strings. Sensitive mapping values whose keys contain `password`, `secret`, `token`, `api_key` or `authorization` are recursively replaced with `<redacted>` in returned payloads. Other strings, including instruction-like text, remain inert data and are preserved exactly.

## Reliability and compatibility

- Processing is deterministic and must not mutate caller-owned records, specs or state.
- An identical `(provider, id)` event is skipped on replay. Reusing the identity for different content is rejected with `identity_conflict`.
- State must survive a JSON round trip. Accept legacy version-1 state shaped as `{"seen_ids": ["provider:id"]}` and migrate it without losing deduplication behavior.
- A malformed record must not prevent valid siblings from being accepted.
- `summarize` accepts either the new batch result or the legacy list of canonical events and returns deterministic `total`, `by_provider`, `by_kind` and sorted unique `entity_keys`.
- Avoid algorithms whose work grows quadratically with the number of records. The production path must handle thousands of events within a normal unit-test budget.

Run the public tests, add useful regression tests if desired, and keep the public API backward compatible. Do not modify `task.md` or existing public tests.
