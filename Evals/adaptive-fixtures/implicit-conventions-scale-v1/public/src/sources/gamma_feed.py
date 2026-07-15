"""Gamma Securities Market notice feed (live, migrated).

Gamma delivers ``{"result": {"rows": [...]}}``; failures arrive as
``{"error": {...}}`` with a normal transport status. Error-shaped or empty
payloads fail loudly (FeedError), like every source.

Gamma is MIGRATED to the shared house flow: each record goes through
core/normalize.house_flow (as_of -> scrub -> resolve, with the per-source
flow counter that run_health checks). A gamma ``amend`` re-issues an earlier
notice with corrected values and is recorded as a restatement.
"""

from ..core import changelog, identity, normalize, rows, text
from ..core.feed_errors import FeedError

_KIND_BY_TYPE = {"amend": "restate"}

FIELD_NOTES = {
    "instrument": "instrument symbol (gamma symbology: hyphenated preferred lines)",
    "type": "gamma's kind vocabulary; only 'amend' needs normalizing",
    "headline": "free-text headline",
    "posted": "ISO date the notice went public",
    "applies": "ISO date the action takes effect",
    "ref": "gamma's stable notice id",
}


def load_events(payload):
    if not isinstance(payload, dict) or "error" in payload:
        raise FeedError("gamma feed returned an error payload: %r" % (payload,))
    raw_rows = (payload.get("result") or {}).get("rows", [])
    if not raw_rows:
        raise FeedError("gamma feed returned zero rows; refusing to load nothing silently")
    events = []
    for raw in raw_rows:
        kind = _KIND_BY_TYPE.get(raw["type"], raw["type"])
        event = {
            "symbol": raw["instrument"],
            "kind": kind,
            "description": text.clean(raw.get("headline", "")),
            "published_at": raw["posted"],
            "effective_at": raw["applies"],
            "issuer": "",
            "venue": "gamma",
            "source": "gamma",
            "natural_key": raw.get("ref") or "%s|%s" % (raw["instrument"], raw["posted"]),
            "revision": 1 if raw["type"] == "amend" else 0,
        }
        normalize.house_flow(event, "gamma")
        event["event_id"] = identity.event_id(
            "gamma", event["natural_key"], event["kind"],
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
