"""Gamma exchange feed (reference).

Gamma delivers ``{"result": {"rows": [...]}}``; failures arrive as
``{"error": {...}}`` with a normal transport status. Consistent with the other
sources: error-shaped or empty payloads fail loudly, the per-record flow is
normalize -> as_of from the published date -> guard.scrub_tokens ->
resolve.resolve_issuer, the change log is append-only (an "amend" is a new
restate row), and rows go through rows.make_row.
"""

from .. import changelog, dates, guard, resolve, rows
from ..feed_errors import FeedError


def load_events(payload):
    if not isinstance(payload, dict) or "error" in payload:
        raise FeedError("gamma feed returned an error payload: %r" % (payload,))
    raw_rows = (payload.get("result") or {}).get("rows", [])
    if not raw_rows:
        raise FeedError("gamma feed returned zero rows; refusing to load nothing silently")
    events = []
    for raw in raw_rows:
        event = {
            "symbol": raw["instrument"],
            "kind": "restate" if raw["type"] == "amend" else raw["type"],
            "description": raw.get("headline", ""),
            "published_at": raw["posted"],
            "effective_at": raw["applies"],
            "issuer": "",
            "venue": "gamma",
        }
        event["as_of"] = dates.as_of_date(event)
        guard.scrub_tokens(event)
        resolve.resolve_issuer(event)
        events.append(event)
    return events


def ingest(payload, table, log):
    for event in load_events(payload):
        changelog.record(log, event)
        table.append(rows.make_row(event))
    return table, log
