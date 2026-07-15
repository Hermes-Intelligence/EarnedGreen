"""Beta exchange feed.

Beta delivers ``{"status": "ok", "records": [...]}``; a failed batch arrives
as ``{"status": "error", ...}`` with the SAME transport status as success.
Like every source, an error-shaped or empty payload fails loudly (FeedError):
loading zero rows silently is the one failure nobody notices.

The per-record flow matches alpha_feed (the house order is deliberate):
normalize -> as_of from dates.as_of_date (published, never effective) ->
guard.scrub_tokens -> resolve.resolve_issuer -> changelog.record (append-only,
restatements are new rows) -> rows.make_row (exact COLUMNS order).
"""

from .. import changelog, dates, guard, resolve, rows
from ..feed_errors import FeedError


def load_events(payload):
    if not isinstance(payload, dict) or payload.get("status") != "ok":
        raise FeedError("beta feed returned an error payload: %r" % (payload,))
    records = payload.get("records", [])
    if not records:
        raise FeedError("beta feed returned zero records; refusing to load nothing silently")
    events = []
    for record in records:
        event = {
            "symbol": record["sym"],
            "kind": "restate" if record.get("restated") else record["act"],
            "description": record.get("text", ""),
            "published_at": record["pub_date"],
            "effective_at": record["eff_date"],
            "issuer": record.get("issuer", ""),
            "venue": "beta",
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
