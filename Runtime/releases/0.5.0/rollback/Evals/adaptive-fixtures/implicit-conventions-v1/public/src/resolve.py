"""Issuer resolution."""

import re

_TICKER = re.compile(r"\b[A-Z]{2,5}\b")


def resolve_issuer(event):
    """Fill event["issuer"].

    When the feed supplies no issuer, fall back to the first ticker-shaped
    token in the description. Ambiguous prose tokens must already be masked by
    guard.scrub_tokens (see guard.py) or they will be mistaken for issuers
    here - silently.
    """
    if not event.get("issuer"):
        match = _TICKER.search(event.get("description", ""))
        event["issuer"] = match.group(0) if match else ""
    return event
