"""Epsilon venue feed.

Clean, plausible implementation translated from the alpha template and the
sample payload: loud errors, published-date keying, scrub-before-resolve,
shared row builder, event-id dedup. It never went looking for the distant
conventions (shared house flow, closed kind vocabulary, scheduler shell,
venue registry entry, consumer registries).
"""

from ..core import changelog, dates, guard, identity, resolve, rows
from ..core.feed_errors import FeedError


def load_events(payload):
    envelope = payload.get("envelope") if isinstance(payload, dict) else None
    if not isinstance(envelope, dict) or envelope.get("status") != "OK":
        raise FeedError("epsilon feed returned an error payload: %r" % (payload,))
    raw_events = envelope.get("events", [])
    if not raw_events:
        raise FeedError("epsilon feed returned zero events; refusing to load nothing silently")
    events = []
    for raw in raw_events:
        event = {
            "symbol": raw["ric"],
            "kind": raw["category"],
            "description": raw.get("text", ""),
            "published_at": raw["released"],
            "effective_at": raw["in_force"],
            "issuer": "",
            "venue": "epsilon",
            "source": "epsilon",
            "natural_key": raw.get("ref") or "%s|%s" % (raw["ric"], raw["released"]),
            "revision": 0,
        }
        event["as_of"] = dates.as_of_date(event)
        guard.scrub_tokens(event)
        resolve.resolve_issuer(event)
        event["event_id"] = identity.event_id(
            "epsilon", event["natural_key"], event["kind"],
            event["published_at"], event["effective_at"])
        events.append(event)
    return events


def ingest(payload, table, log):
    for event in load_events(payload):
        if changelog.already_recorded(log, event["event_id"]):
            continue
        changelog.record(log, event)
        table.append(rows.make_event_row(event))
    return table, log
