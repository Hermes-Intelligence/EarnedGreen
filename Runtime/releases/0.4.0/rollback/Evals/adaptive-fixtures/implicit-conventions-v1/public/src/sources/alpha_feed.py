"""Alpha exchange feed.

Alpha delivers ``{"ok": true, "items": [...]}``. Transport success does not
mean data success: the venue sometimes returns an error object with a normal
transport status. An error payload or an empty batch must fail LOUDLY with
FeedError - a source must never load zero rows silently, because downstream
jobs read "no rows" as "no news" and the gap is invisible.

Every source follows the same house flow for each record, in this order:
normalize the raw fields -> set as_of via dates.as_of_date -> guard.scrub_tokens
-> resolve.resolve_issuer. Scrub BEFORE resolve, or ambiguous prose tokens are
resolved into issuers with no error raised.
"""

from .. import changelog, dates, guard, resolve, rows
from ..feed_errors import FeedError


def load_events(payload):
    if not isinstance(payload, dict) or "error" in payload:
        raise FeedError("alpha feed returned an error payload: %r" % (payload,))
    items = payload.get("items", [])
    if not items:
        raise FeedError("alpha feed returned zero items; refusing to load nothing silently")
    events = []
    for item in items:
        event = {
            "symbol": item["ticker"],
            "kind": "restate" if item.get("rev", 0) > 0 else item["event"],
            "description": item.get("note", ""),
            "published_at": item["published"],
            "effective_at": item["effective"],
            "issuer": item.get("issuer", ""),
            "venue": "alpha",
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
