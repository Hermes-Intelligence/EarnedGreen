"""Epsilon venue feed (independent second reference).

Authored from task.md plus the public code alone; every decision keyed to a
discoverable in-repo convention (see ALT-NOTES.json). Same behavior as the
primary reference, deliberately different structure: a field-translation
table, a functional per-record pipeline and comprehension-style loading.
"""

from ..core import changelog, identity, normalize, rows
from ..core.feed_errors import FeedError

_FIELDS = (
    # (event key, raw key, default)
    ("symbol", "ric", None),
    ("description", "text", ""),
    ("published_at", "released", None),
    ("effective_at", "in_force", None),
)

_KINDS = {"halt": "halt", "resume": "resume", "correction": "restate"}


def _translate(raw):
    event = {key: raw.get(source, default) if default is not None else raw[source]
             for key, source, default in _FIELDS}
    category = raw["category"]
    event.update({
        "kind": _KINDS.get(category, category),
        "issuer": "",
        "venue": "epsilon",
        "source": "epsilon",
        "natural_key": raw.get("ref") or "|".join((raw["ric"], raw["released"])),
        "revision": int(category == "correction"),
    })
    normalize.house_flow(event, "epsilon")
    event["event_id"] = identity.event_id(
        "epsilon", event["natural_key"], event["kind"],
        event["published_at"], event["effective_at"])
    return event


def load_events(payload):
    envelope = (payload or {}).get("envelope") if isinstance(payload, dict) else None
    if not isinstance(envelope, dict) or envelope.get("status") != "OK":
        raise FeedError("epsilon feed error payload: %r" % (payload,))
    if not envelope.get("events"):
        raise FeedError("epsilon feed delivered an empty batch; failing loudly by house rule")
    return [_translate(raw) for raw in envelope["events"]]


def ingest(payload, table, log):
    for event in load_events(payload):
        if not changelog.already_recorded(log, event["event_id"]):
            changelog.record(log, event)
            table.append(rows.make_event_row(event))
    return table, log
