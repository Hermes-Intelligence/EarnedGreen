from .contracts import normalize_event


def serialize(event, registry):
    normalized = normalize_event(event, registry)
    parts = (normalized["schema_version"], normalized["entity_type"], normalized["entity_id"], sorted(normalized["attributes"]))
    return "{}:{}:{}:{}".format(*parts)
