"""Alpha Exchange notice feed (live).

Alpha delivers ``{"ok": true, "items": [...]}``. Transport success does not
mean data success: the venue sometimes returns an error object with a normal
transport status. An error payload or an empty batch must fail LOUDLY with
FeedError - a source must never load zero rows silently, because downstream
jobs read "no rows" as "no news" and the gap is invisible until a client
asks why a halt is missing.

Per-record flow (the house order, kept inline here for historical reasons;
this module predates core/normalize.house_flow and is scheduled for
migration - see the MIGRATION note in core/normalize.py):

    normalize raw fields -> as_of from dates.as_of_date (published, never
    effective) -> guard.scrub_tokens -> resolve.resolve_issuer
    -> identity.event_id over the signal fields -> skip when
    changelog.already_recorded -> changelog.record -> rows.make_event_row

Alpha marks a re-issued notice with a bumped ``rev`` counter on the same
``key``; a bumped rev is a restatement (kind "restate", a NEW log row).
"""

from ..core import changelog, dates, guard, identity, resolve, rows, text
from ..core.feed_errors import FeedError

FIELD_NOTES = {
    "ticker": "instrument symbol (alpha symbology, see reference/symbology.py)",
    "event": "alpha's own kind vocabulary; matches the closed vocabulary directly",
    "note": "free-text headline; boilerplate-prefixed on some days",
    "published": "ISO date the notice went public",
    "effective": "ISO date the action takes effect",
    "rev": "revision counter; > 0 means the notice re-issues an earlier key",
    "key": "alpha's stable notice id",
}


def load_events(payload):
    if not isinstance(payload, dict) or "error" in payload or not payload.get("ok"):
        raise FeedError("alpha feed returned an error payload: %r" % (payload,))
    items = payload.get("items", [])
    if not items:
        raise FeedError("alpha feed returned zero items; refusing to load nothing silently")
    events = []
    for item in items:
        revision = int(item.get("rev", 0))
        event = {
            "symbol": item["ticker"],
            "kind": "restate" if revision > 0 else item["event"],
            "description": text.clean(item.get("note", "")),
            "published_at": item["published"],
            "effective_at": item["effective"],
            "issuer": item.get("issuer", ""),
            "venue": "alpha",
            "source": "alpha",
            "natural_key": item.get("key") or "%s|%s" % (item["ticker"], item["published"]),
            "revision": revision,
        }
        event["as_of"] = dates.as_of_date(event)
        guard.scrub_tokens(event)
        resolve.resolve_issuer(event)
        event["event_id"] = identity.event_id(
            "alpha", event["natural_key"], event["kind"],
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
