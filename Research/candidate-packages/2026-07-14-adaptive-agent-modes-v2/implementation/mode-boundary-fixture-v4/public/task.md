# Adaptive contract evolution (v4)

Evolve the ingestion contract from the legacy `parse_record` API to a
registry-driven `normalize_event`, without replacing the public API with a
sample-derived special case. The implementation must generalize beyond the
examples in the public tests.

## Core requirements

- Add `normalize_event(event, registry)` returning exactly `{"entity_type", "entity_id", "attributes", "schema_version"}`, where `schema_version` is the integer `3`.
- Treat entity types and attribute names as open-world: they are non-blank strings that may appear for the first time in production; resolve optional per-type behavior through the runtime `registry`; do not encode discovered samples as an allowlist or regex alternation.
- When a valid event's type has a registry entry, apply that callable to a deep copy of the attributes. A handler that returns anything other than a dictionary is a malformed event and is rejected.
- When a valid event's type is not present in the registry, `normalize_event` must not raise: it returns the attributes unchanged (deep-copied) and increments `unknown_entity_type` exactly once for the first sighting of that identity.
- Reject non-dictionaries, missing/blank/non-string identifiers, non-dictionary attributes, extra or missing event keys, and registry entries that are not callables by raising `TypeError` or `ValueError`.
- Preserve caller-owned input without mutation, including nested attributes. The returned attributes must also be independent of the caller's objects, so mutating the result never changes the input.
- Preserve `parse_record(record)` as a backward-compatible wrapper with its existing legacy behavior; it takes no registry, records no telemetry, and does not gain the `schema_version` field.
- Update both `render_primary(event, registry)` and `render_audit(event, registry)` to the normalized contract.
- Record telemetry through `metrics.increment(name)` only at the boundaries defined below.
- Document the extension path and compatibility behavior in `README.md`; semantic wording is sufficient.
- Add focused tests, including at least one unseen Unicode entity type and one malformed input.

## Behavioral details

These details are part of the contract even though they live on rare paths and
in prose. A careful implementation must track them; a happy-path pass tends to
miss them.

Registered handlers run untrusted, data-dependent code and can fail on some
inputs. When a registered handler raises any exception, `normalize_event` does
not propagate it and does not treat the event as malformed: it increments
`handler_error` exactly once, falls back to the deep-copied original attributes,
and returns the normal envelope. This degraded fallback yields the same
attributes as an unresolved type but is counted under its own metric, never as
`unknown_entity_type`.

Entity types are compared exactly: the value used for the registry lookup and
for `entity_type` in the envelope is the original string, never a trimmed or
otherwise rewritten form, even though the blank check uses its stripped length.
For example, an event whose type is `"customer "` (with a trailing space) does
not match a handler registered under `"customer"`; it is an unresolved type.

Ingestion is retried and events are replayed, so the same unresolved event can
reach `normalize_event` more than once in a process. The unknown-type telemetry
is per identity, not per call: the first time an unresolved `(entity_type, entity_id)` pair is seen it increments `unknown_entity_type`, but a later re-ingestion of that same unresolved pair is a repeat and increments `unknown_repeat` instead, never `unknown_entity_type` a second time. The dedup ledger of seen unresolved identities lives for the process lifetime and is independent of the counter reset. Only unresolved sightings participate; a resolved type and the handler-error fallback never touch the ledger.

## Downstream consumers

The evolved contract has consumers beyond the two render functions, and every
consumer must resolve through `normalize_event` and carry `schema_version`, even
when it reaches the contract indirectly.

The audit export path `exporter.export_digest(records, registry)` serializes two hops away through `serializer.serialize`; it must adopt the normalized contract, pass the registry through, and include `schema_version` in each serialized line. It is a consumer of the evolved contract just like the render functions, even though it is reached indirectly.

The cache snapshot path `snapshot.build_snapshot(events, registry)` builds each line two hops away through `digest_helper.digest_line`; it too must adopt the normalized contract, pass the registry through, and carry `schema_version` in every snapshot line. It is a separate indirect consumer from the audit export and must be migrated on its own.

## Telemetry boundaries

- Every rejection at the `normalize_event` boundary increments `malformed_event` exactly once; the handler-error fallback is not a rejection and increments `handler_error` instead.
- The first unresolved sighting of an identity increments `unknown_entity_type` exactly once; a repeated unresolved sighting increments `unknown_repeat` instead.

Do not modify `task.md` or existing public tests.
