# Ingestion contract, evolved

Per-type behavior is optional and lives in the runtime registry, so the contract stays open to entity types nobody has seen yet: a type without a registry entry is counted as `unknown_entity_type` and its attributes flow through untouched, with no code deployment required.

Compatibility: legacy callers keep using `parse_record`, which behaves exactly as before while consumers migrate to `normalize_event`.
