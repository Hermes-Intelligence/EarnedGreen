from .contracts import parse_record


def serialize(record):
    """Legacy serializer: flattens a record into an audit-export line.

    Retained from before the contract evolution. It still resolves records
    through the legacy `parse_record` path and emits no schema version.
    """
    parsed = parse_record(record)
    return f"{parsed['entity_type']}:{parsed['entity_id']}:{sorted(parsed['attributes'])}"
