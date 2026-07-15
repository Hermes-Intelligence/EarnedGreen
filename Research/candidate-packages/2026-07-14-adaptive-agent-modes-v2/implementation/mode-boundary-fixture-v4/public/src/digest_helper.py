from .contracts import parse_record


def digest_line(record):
    """Legacy snapshot helper: renders one record into a cache-snapshot line.

    Retained from before the contract evolution. It resolves the record through
    the legacy `parse_record` path and emits no schema version. It is the
    intermediary between `snapshot.build_snapshot` and normalization.
    """
    parsed = parse_record(record)
    return f"{parsed['entity_type']}|{parsed['entity_id']}|{sorted(parsed['attributes'])}"
