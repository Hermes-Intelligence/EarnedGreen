"""Gamma exchange feed.

Clean, plausible implementation written from the task text alone: it wires the
gamma payload shape into the pipeline, uses the shared row builder, applies the
token guard, and treats an "amend" as a correction of the earlier entry. It
passes the public tests. It also violates four implicit house conventions it
never went looking for: it resolves the issuer BEFORE scrubbing tokens, keys
as_of by the effective ("applies") date, updates the change log in place on
amendments, and returns an empty batch instead of failing loudly on
error-shaped or zero-row payloads.
"""

from .. import changelog, guard, resolve, rows


def load_events(payload):
    raw_rows = []
    if isinstance(payload, dict):
        raw_rows = (payload.get("result") or {}).get("rows", [])
    events = []
    for raw in raw_rows:
        event = {
            "symbol": raw["instrument"],
            "kind": "restate" if raw["type"] == "amend" else raw["type"],
            "description": raw.get("headline", ""),
            "published_at": raw["posted"],
            "effective_at": raw["applies"],
            "issuer": "",
            "venue": "gamma",
            "as_of": raw["applies"],
        }
        resolve.resolve_issuer(event)
        guard.scrub_tokens(event)
        events.append(event)
    return events


def ingest(payload, table, log):
    for event in load_events(payload):
        if event["kind"] == "restate":
            replaced = False
            for index, entry in enumerate(log):
                if entry.get("symbol") == event["symbol"]:
                    log[index] = {"symbol": event["symbol"], "kind": event["kind"], "as_of": event["as_of"]}
                    replaced = True
                    break
            for index, row in enumerate(table):
                if event["symbol"] in str(row):
                    table[index] = rows.make_row(event)
                    break
            if replaced:
                continue
        changelog.record(log, event)
        table.append(rows.make_row(event))
    return table, log
