from .contracts import normalize_event


def render_primary(event, registry):
    # Deliberately different from hidden/reference (`customer:2`) and from the
    # live arms (`customer:2:3`, `customer:2:v3`): a bracket/hash layout.
    parsed = normalize_event(event, registry)
    return f"entity[{parsed['entity_type']}]#{parsed['entity_id']}"


def render_audit(event, registry):
    # Deliberately different key-list rendering: slash-joined bare keys inside
    # an angle-bracketed record, no Python list repr.
    parsed = normalize_event(event, registry)
    keys = "/".join(sorted(parsed["attributes"]))
    return f"<audit type={parsed['entity_type']} attrs={keys}>"
