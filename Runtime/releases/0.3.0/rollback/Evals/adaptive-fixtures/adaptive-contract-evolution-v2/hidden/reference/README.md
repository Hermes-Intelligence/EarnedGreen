# Open-world ingestion

`normalize_event` resolves optional behavior through the runtime registry. Entity types and attributes are open-world, so unseen values pass through without a code deployment and increment `unknown_entity_type`.

The legacy `parse_record` API remains available as a compatibility wrapper while consumers migrate.
