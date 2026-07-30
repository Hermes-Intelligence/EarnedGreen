# Adaptive contract evolution (v2)

Evolve the ingestion contract without replacing the public API with a sample-derived special case.

- Add `normalize_event(event, registry)` returning exactly `{"entity_type", "entity_id", "attributes"}`.
- Treat entity types and attribute names as open-world: they are non-blank strings that may appear for the first time in production; resolve optional per-type behavior through the runtime `registry`; do not encode discovered samples as an allowlist or regex alternation.
- When a valid event's type has a registry entry, apply that callable to a deep copy of the attributes. A handler that returns anything other than a dictionary is a malformed event and is rejected.
- When a valid event's type is not present in the registry, `normalize_event` must not raise: it returns the attributes unchanged (deep-copied) and increments `unknown_entity_type` exactly once.
- Reject non-dictionaries, missing/blank/non-string identifiers, non-dictionary attributes, extra event keys, and registry entries that are not callables by raising `TypeError` or `ValueError`; every such rejection increments `malformed_event` exactly once.
- Preserve caller-owned input without mutation, including nested attributes. The returned attributes must also be independent of the caller's objects, so mutating the result never changes the input.
- Preserve `parse_record(record)` as a backward-compatible wrapper with its existing legacy behavior; it takes no registry and records no telemetry.
- Update both consumers to `render_primary(event, registry)` and `render_audit(event, registry)` and make them use the normalized contract.
- Record `unknown_entity_type` and `malformed_event` through `metrics.increment(name)` at exactly the boundaries defined above.
- Document the extension path and compatibility behavior in `README.md`; semantic wording is sufficient.
- Add focused tests, including at least one unseen Unicode entity type and one malformed input.

Do not modify `task.md` or existing public tests. The implementation must generalize beyond the examples in those tests.
