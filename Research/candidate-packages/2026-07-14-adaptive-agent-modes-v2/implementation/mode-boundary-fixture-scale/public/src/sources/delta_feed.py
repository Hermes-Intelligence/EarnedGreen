"""Delta Exchange Group notice feed (live, migrated).

Delta delivers ``{"meta": {"status": "success"}, "data": {"notices": [...]}}``
and reports failures as ``{"meta": {"status": "failure", ...}}`` on the same
transport status. Error-shaped or empty payloads fail loudly (FeedError).

Delta is MIGRATED to the shared house flow (core/normalize.house_flow).
Delta's action vocabulary is venue-specific and is normalized to the closed
change-log vocabulary before recording: suspension -> halt, reinstatement ->
resume, revision -> restate (a revision re-issues an earlier docket with
corrected values).
"""

from ..core import changelog, identity, normalize, rows, text
from ..core.feed_errors import FeedError

_KIND_BY_ACTION = {
    "suspension": "halt",
    "reinstatement": "resume",
    "admission": "listing",
    "removal": "delisting",
    "revision": "restate",
}

FIELD_NOTES = {
    "code": "romanized 3-letter instrument code (delta symbology)",
    "action": "delta's own vocabulary; ALWAYS normalized via _KIND_BY_ACTION",
    "summary": "free-text summary, often boilerplate-prefixed",
    "date_public": "ISO date the notice went public",
    "date_effect": "ISO date the action takes effect",
    "docket": "delta's stable docket id",
}


def load_events(payload):
    meta = payload.get("meta") if isinstance(payload, dict) else None
    if not isinstance(meta, dict) or meta.get("status") != "success":
        raise FeedError("delta feed returned an error payload: %r" % (payload,))
    notices = (payload.get("data") or {}).get("notices", [])
    if not notices:
        raise FeedError("delta feed returned zero notices; refusing to load nothing silently")
    events = []
    for notice in notices:
        action = notice["action"]
        event = {
            "symbol": notice["code"],
            "kind": _KIND_BY_ACTION.get(action, action),
            "description": text.clean(notice.get("summary", "")),
            "published_at": notice["date_public"],
            "effective_at": notice["date_effect"],
            "issuer": "",
            "venue": "delta",
            "source": "delta",
            "natural_key": notice.get("docket") or "%s|%s" % (notice["code"], notice["date_public"]),
            "revision": 1 if action == "revision" else 0,
        }
        normalize.house_flow(event, "delta")
        event["event_id"] = identity.event_id(
            "delta", event["natural_key"], event["kind"],
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
