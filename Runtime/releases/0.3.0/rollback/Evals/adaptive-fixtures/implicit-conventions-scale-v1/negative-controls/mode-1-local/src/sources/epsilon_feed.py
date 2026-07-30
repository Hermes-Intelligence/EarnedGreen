"""Epsilon venue feed: minimal naive wiring (weak control).

Translates the epsilon payload straight into ad-hoc dict rows: no shared row
builder, no house flow, no guard, no issuer resolution, no change log, no
dedup, effective-date keying, and silent empty results on error payloads.
"""


def load_events(payload):
    raw_events = []
    if isinstance(payload, dict):
        raw_events = (payload.get("envelope") or {}).get("events", [])
    return [
        {"symbol": raw["ric"], "kind": raw["category"], "date": raw.get("in_force")}
        for raw in raw_events
    ]


def ingest(payload, table, log):
    for event in load_events(payload):
        table.append(event)
    return table, log
