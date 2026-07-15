"""Shared product-table row contract.

COLUMNS is load-bearing: downstream consumers index rows by POSITION, not by
name (see reports.py-style consumers in the wider system). Every source must
emit rows through make_row so the order never drifts. Adding, removing or
reordering a column is a breaking change for every consumer.
"""

COLUMNS = ("as_of", "symbol", "kind", "issuer", "venue", "masked_tokens", "published_at", "effective_at")


def make_row(event):
    """Build one product-table row in exact COLUMNS order."""
    return (
        event["as_of"],
        event["symbol"],
        event["kind"],
        event.get("issuer", ""),
        event.get("venue", ""),
        tuple(event.get("masked_tokens", ())),
        event["published_at"],
        event["effective_at"],
    )
