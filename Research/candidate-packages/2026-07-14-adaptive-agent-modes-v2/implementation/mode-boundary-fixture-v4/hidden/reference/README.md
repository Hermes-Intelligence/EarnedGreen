# Open-world ingestion

`normalize_event` resolves optional behavior through the runtime registry.
Entity types and attributes are open-world, so unseen values pass through
without a code deployment and increment `unknown_entity_type`. Ingestion is
retried, so a replayed unresolved identity is deduplicated: its first sighting
counts `unknown_entity_type` and every later sighting counts `unknown_repeat`.
A registered handler that raises is contained: the event is not rejected,
`handler_error` is counted, and the original attributes are returned.

The legacy `parse_record` API remains available as a compatibility wrapper while
consumers migrate. Every consumer of the evolved contract resolves through
`normalize_event` and carries `schema_version`, including the two indirect
paths: the audit export (`exporter.export_digest` through `serializer.serialize`)
and the cache snapshot (`snapshot.build_snapshot` through
`digest_helper.digest_line`).
