from .contracts import normalize_event


def serialize(event, registry):
    """Serialize an event through the evolved contract, including schema_version."""
    parsed = normalize_event(event, registry)
    return f"{parsed['schema_version']}:{parsed['entity_type']}:{parsed['entity_id']}:{sorted(parsed['attributes'])}"
