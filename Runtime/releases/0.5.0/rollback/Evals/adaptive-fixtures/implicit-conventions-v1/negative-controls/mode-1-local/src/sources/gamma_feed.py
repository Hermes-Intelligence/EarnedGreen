"""Gamma exchange feed: minimal naive wiring (weak control).

Translates the gamma payload straight into ad-hoc dict rows: no shared row
builder, no token guard, no issuer resolution, no change log, effective-date
keying, and silent empty results on error payloads.
"""


def load_events(payload):
    raw_rows = []
    if isinstance(payload, dict):
        raw_rows = (payload.get("result") or {}).get("rows", [])
    return [
        {"symbol": raw["instrument"], "kind": raw["type"], "date": raw.get("applies")}
        for raw in raw_rows
    ]


def ingest(payload, table, log):
    for event in load_events(payload):
        table.append(event)
    return table, log
