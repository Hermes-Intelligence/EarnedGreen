from .contracts import normalize_event


def render_primary(event, registry):
    normalized = normalize_event(event, registry)
    return "{entity_type}:{entity_id}".format(**normalized)


def render_audit(event, registry):
    normalized = normalize_event(event, registry)
    return "AUDIT {} {}".format(normalized["entity_type"], sorted(normalized["attributes"]))
