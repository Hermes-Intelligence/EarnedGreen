"""Beta Boerse notice feed (live).

Beta delivers ``{"status": "ok", "records": [...]}``; a failed batch arrives
as ``{"status": "error", ...}`` with the SAME transport status as success.
Like every source, an error-shaped or empty payload fails loudly (FeedError):
loading zero rows silently is the one failure nobody notices.

Per-record flow: identical house order to alpha_feed, also still inline
(both legacy modules are grandfathered until their migration to
core/normalize.house_flow lands - see core/normalize.py). Beta marks a
re-issued notice with ``restated: true`` on the same ``ref``.
"""

from ..core import changelog, dates, guard, identity, resolve, rows, text
from ..core.feed_errors import FeedError

FIELD_NOTES = {
    "sym": "instrument symbol (beta symbology: numeric line extensions)",
    "act": "beta's kind vocabulary; matches the closed vocabulary directly",
    "text": "free-text notice body",
    "pub_date": "ISO date the notice went public",
    "eff_date": "ISO date the action takes effect",
    "restated": "true when the record re-issues an earlier ref",
    "ref": "beta's stable notice id",
}


def load_events(payload):
    if not isinstance(payload, dict) or payload.get("status") != "ok":
        raise FeedError("beta feed returned an error payload: %r" % (payload,))
    records = payload.get("records", [])
    if not records:
        raise FeedError("beta feed returned zero records; refusing to load nothing silently")
    events = []
    for record in records:
        restated = bool(record.get("restated"))
        event = {
            "symbol": record["sym"],
            "kind": "restate" if restated else record["act"],
            "description": text.clean(record.get("text", "")),
            "published_at": record["pub_date"],
            "effective_at": record["eff_date"],
            "issuer": record.get("issuer", ""),
            "venue": "beta",
            "source": "beta",
            "natural_key": record.get("ref") or "%s|%s" % (record["sym"], record["pub_date"]),
            "revision": 1 if restated else 0,
        }
        event["as_of"] = dates.as_of_date(event)
        guard.scrub_tokens(event)
        resolve.resolve_issuer(event)
        event["event_id"] = identity.event_id(
            "beta", event["natural_key"], event["kind"],
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
