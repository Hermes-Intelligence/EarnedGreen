# Registry-driven ingestion (evolved contract)

The evolved `normalize_event` looks up optional per-type behavior in the runtime
registry. Because types and attribute keys are open-world, an unregistered type
is not an error: its attributes pass through untouched and `unknown_entity_type`
is recorded. A handler that blows up on a particular input is likewise contained
rather than fatal -- `handler_error` is recorded and the original attributes are
returned.

Compatibility: the older `parse_record` entry point is kept unchanged so callers
can migrate gradually.
