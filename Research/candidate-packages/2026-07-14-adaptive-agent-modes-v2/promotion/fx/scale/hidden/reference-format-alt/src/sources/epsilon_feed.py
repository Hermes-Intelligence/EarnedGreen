"""Epsilon Securities Exchange notice feed (reference).

Epsilon delivers ``{"envelope": {"status": "OK", "events": [...]}}``; a
failed batch arrives with a non-OK status on the same transport status.
Consistent with the other sources: error-shaped or empty payloads fail
loudly, the per-record flow goes through the shared house flow
(core/normalize.house_flow - epsilon is a NEW source, so it starts
migrated), the change log stays append-only (a "correction" re-issues an
earlier notice and is recorded as a NEW restate row), and rows go through
rows.make_event_row in exact EVENT_COLUMNS order.
"""

from ..core import changelog, identity, normalize, rows
from ..core.feed_errors import FeedError

_KIND_BY_CATEGORY = {"correction": "restate"}


def load_events(payload):
    envelope = payload.get("envelope") if isinstance(payload, dict) else None
    if not isinstance(envelope, dict) or envelope.get("status") != "OK":
        raise FeedError("epsilon feed returned an error payload: %r" % (payload,))
    raw_events = envelope.get("events") or []
    if not raw_events:
        raise FeedError("epsilon feed returned zero events; refusing to load nothing silently")
    events = []
    for raw in raw_events:
        category = raw["category"]
        event = {
            "symbol": raw["ric"],
            "kind": _KIND_BY_CATEGORY.get(category, category),
            "description": raw.get("text", ""),
            "published_at": raw["released"],
            "effective_at": raw["in_force"],
            "issuer": "",
            "venue": "epsilon",
            "source": "epsilon",
            "natural_key": raw.get("ref") or "%s|%s" % (raw["ric"], raw["released"]),
            "revision": 1 if category == "correction" else 0,
        }
        normalize.house_flow(event, "epsilon")
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
