# Open-world ingestion (format-adversary reference)

Semantically identical to `hidden/reference`, but every serialized consumer uses
a deliberately different format. `normalize_event` resolves optional behavior
through the runtime registry; entity types and attributes are open-world, so an
unseen value passes through without a deployment and increments
`unknown_entity_type`, while a replayed unresolved identity is deduplicated into
`unknown_repeat`. A registered handler that raises is contained: the event is not
rejected, `handler_error` is counted, and the original attributes are returned.

The legacy `parse_record` API stays available as a compatibility wrapper while
consumers migrate. Every consumer resolves through `normalize_event` and carries
`schema_version`, including the two indirect paths: the audit export
(`exporter.export_digest` through `serializer.serialize`) and the cache snapshot
(`snapshot.build_snapshot` through `digest_helper.digest_line`). Only the surface
serialization differs from the primary reference; the substance is the same.
