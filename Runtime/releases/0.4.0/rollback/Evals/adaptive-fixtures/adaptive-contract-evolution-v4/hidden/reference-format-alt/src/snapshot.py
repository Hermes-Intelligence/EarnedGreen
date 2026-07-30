from .digest_helper import digest_line


def build_snapshot(events, registry):
    """Cache snapshot layer, registry-aware and schema-versioned."""
    return {event["id"]: digest_line(event, registry) for event in events}
