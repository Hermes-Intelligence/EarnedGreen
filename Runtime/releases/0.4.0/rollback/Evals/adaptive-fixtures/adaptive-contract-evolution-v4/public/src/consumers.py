from .contracts import parse_record


def render_primary(record):
    parsed = parse_record(record)
    return f"{parsed['entity_type']}:{parsed['entity_id']}"


def render_audit(record):
    parsed = parse_record(record)
    return f"AUDIT {parsed['entity_type']} {sorted(parsed['attributes'])}"
