"""Gamma exchange feed (alternative reference).

Authored independently from task.md plus the existing code alone, to prove the
discoverable conventions pin one behavior. Same semantics as the primary
reference, different structure: a field-translation table and helper pipeline
instead of an inline loop.
"""

from .. import changelog, dates, guard, resolve, rows
from ..feed_errors import FeedError

_KIND_BY_TYPE = {"amend": "restate"}
_FIELDS = (
    ("symbol", "instrument"),
    ("description", "headline"),
    ("published_at", "posted"),
    ("effective_at", "applies"),
)


def _translate(raw):
    event = {target: raw.get(source, "") for target, source in _FIELDS}
    event["kind"] = _KIND_BY_TYPE.get(raw.get("type"), raw.get("type"))
    event["issuer"] = ""
    event["venue"] = "gamma"
    event["as_of"] = dates.as_of_date(event)
    return resolve.resolve_issuer(guard.scrub_tokens(event))


def load_events(payload):
    if not isinstance(payload, dict) or payload.get("error") is not None:
        raise FeedError("gamma payload is error-shaped; refusing to load it silently: %r" % (payload,))
    raw_rows = (payload.get("result") or {}).get("rows") or []
    if not raw_rows:
        raise FeedError("gamma payload contains zero rows; an empty batch is a failure, not an absence of news")
    return [_translate(raw) for raw in raw_rows]


def ingest(payload, table, log):
    events = load_events(payload)
    for event in events:
        changelog.record(log, event)
        table.append(rows.make_row(event))
    return table, log
