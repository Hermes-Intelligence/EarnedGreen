"""Shared event-row contract for the WIRE events table.

EVENT_COLUMNS is load-bearing: downstream consumers index event rows by
POSITION, not by name (positions_report, exposure_export and the saved client
exports scripted against column offsets). Every source must emit rows through
make_event_row so the order never drifts. Adding, removing or reordering a
column is a breaking change for every consumer and for every export a client
has already scripted against.

Column notes:
- as_of is always the knowledge date (see core/dates.py).
- event_id is the state hash from core/identity.py.
- masked_tokens is the tuple recorded by core/guard.py.
- venue and source are registry codes (see reference/venues.py and the
  pipeline registry).
"""

EVENT_COLUMNS = (
    "as_of",          # 0  knowledge date (published), never effective
    "event_id",       # 1  state hash (identity.event_id)
    "symbol",         # 2  instrument symbol on the venue
    "kind",           # 3  closed vocabulary (core/changelog.KINDS)
    "issuer",         # 4  resolved issuer token ("" when unresolved)
    "venue",          # 5  venue code (reference/venues.py)
    "source",         # 6  ingesting source code (pipeline registry key)
    "masked_tokens",  # 7  ambiguous tokens masked by the guard
    "published_at",   # 8  when the venue made the event public
    "effective_at",   # 9  when the action takes effect on the venue
    "natural_key",    # 10 stable id of the underlying notice
    "revision",       # 11 revision counter of the notice (0 = original)
)


def make_event_row(event):
    """Build one events-table row in exact EVENT_COLUMNS order."""
    return (
        event["as_of"],
        event["event_id"],
        event["symbol"],
        event["kind"],
        event.get("issuer", ""),
        event.get("venue", ""),
        event.get("source", ""),
        tuple(event.get("masked_tokens", ())),
        event["published_at"],
        event["effective_at"],
        event.get("natural_key", ""),
        int(event.get("revision", 0)),
    )
