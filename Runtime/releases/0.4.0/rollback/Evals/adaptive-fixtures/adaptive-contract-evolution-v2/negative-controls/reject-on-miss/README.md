# Open-world ingestion

`normalize_event` resolves optional behavior through the runtime registry, keeping the contract open to new entity types; unknown types increment `unknown_entity_type`.

The legacy `parse_record` API remains available as a compatibility wrapper while consumers migrate.
