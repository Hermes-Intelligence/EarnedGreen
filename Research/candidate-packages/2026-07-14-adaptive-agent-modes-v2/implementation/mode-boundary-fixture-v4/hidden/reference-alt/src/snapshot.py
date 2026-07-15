from .digest_helper import digest_line


def build_snapshot(events, registry):
    snapshot = {}
    for event in events:
        snapshot[event["id"]] = digest_line(event, registry)
    return snapshot
