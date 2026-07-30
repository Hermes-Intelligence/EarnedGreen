from .contracts import normalize_event


def digest_line(event, registry):
    normalized = normalize_event(event, registry)
    parts = (normalized["schema_version"], normalized["entity_type"], normalized["entity_id"], sorted(normalized["attributes"]))
    return "v{}|{}|{}|{}".format(*parts)
