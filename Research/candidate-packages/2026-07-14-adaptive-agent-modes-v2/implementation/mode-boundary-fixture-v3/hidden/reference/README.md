# Open-world ingestion

`normalize_event` resolves optional behavior through the runtime registry.
Entity types and attributes are open-world, so unseen values pass through
without a code deployment and increment `unknown_entity_type`. A registered
handler that raises is contained: the event is not rejected, `handler_error` is
counted, and the original attributes are returned.

The legacy `parse_record` API remains available as a compatibility wrapper while
consumers migrate. Every consumer of the evolved contract, including the audit
export path (`exporter.export_digest`), resolves through `normalize_event` and
carries `schema_version`.
