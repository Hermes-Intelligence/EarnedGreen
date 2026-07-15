from .contracts import normalize_event


def render_primary(event, registry):
    parsed=normalize_event(event,registry); return f"{parsed['entity_type']}:{parsed['entity_id']}"


def render_audit(event, registry):
    parsed=normalize_event(event,registry); return f"AUDIT {parsed['entity_type']} {sorted(parsed['attributes'])}"
