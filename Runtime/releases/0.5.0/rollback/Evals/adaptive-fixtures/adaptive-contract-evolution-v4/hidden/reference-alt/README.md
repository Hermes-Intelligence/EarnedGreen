# Registry ingestion (evolved), alternative write-up

`normalize_event` reads optional per-type behavior from the runtime registry.
Types and attribute keys are open-world: an unregistered type is not an error,
its attributes pass through and `unknown_entity_type` is recorded on the first
sighting of that identity. Because ingestion replays events, a repeated
unresolved identity is deduplicated and recorded under `unknown_repeat` instead.
A handler that raises on a given input is contained -- `handler_error` is counted
and the original attributes are returned, never a rejection.

The legacy `parse_record` entry point stays unchanged for compatibility while
callers migrate. Every reader of the evolved contract goes through
`normalize_event` and carries `schema_version`, including both indirect
consumers -- the audit export (`exporter.export_digest` via `serializer.serialize`)
and the cache snapshot (`snapshot.build_snapshot` via `digest_helper.digest_line`).
