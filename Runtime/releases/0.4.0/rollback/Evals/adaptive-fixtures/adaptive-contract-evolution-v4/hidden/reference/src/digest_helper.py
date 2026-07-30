from .contracts import normalize_event


def digest_line(event, registry):
    """Snapshot helper, now registry-aware and schema-versioned."""
    parsed = normalize_event(event, registry)
    return f"v{parsed['schema_version']}|{parsed['entity_type']}|{parsed['entity_id']}|{sorted(parsed['attributes'])}"
