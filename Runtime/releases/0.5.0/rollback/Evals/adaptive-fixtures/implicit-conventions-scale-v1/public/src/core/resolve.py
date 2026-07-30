"""Issuer extraction and the issuer -> ticker resolution ladder.

resolve_issuer fills event["issuer"] from the description when the feed
supplies none. Ambiguous prose tokens must already be masked by
guard.scrub_tokens (see core/guard.py) or they will be mistaken for issuers
here - silently.

resolve_ticker maps an issuer token to a tradable ticker through the house
ladder, in order:

    normalize -> exact canonical (reference/issuers.ISSUER_TICKERS)
    -> alias (reference/issuers.ALIASES)
    -> containment (guarded by reference/ambiguity.AMBIGUOUS_BARE and a
       length floor, so generic brand words never containment-match)
    -> fuzzy (difflib ratio against the canonical universe, high floor)
    -> parent chain (reference/issuers.PARENTS)
    -> unresolved (None)

Unresolved issuers are NEVER guessed into a ticker; they stay attributed to
the venue bucket in the exposure table, so nothing is mis-attributed to a
public ticker. build_exposure rebuilds the exposure rows from the events
table; it is idempotent and safe to re-run (the resolution stage in the
scheduler calls it after all source shells have loaded).
"""

import difflib
import re

from ..reference import ambiguity, issuers

_TICKER = re.compile(r"\b[A-Z]{2,5}\b")
_FUZZY_FLOOR = 0.92


def resolve_issuer(event):
    """Fill event["issuer"] from the description when the feed omits it."""
    if not event.get("issuer"):
        match = _TICKER.search(event.get("description", ""))
        event["issuer"] = match.group(0) if match else ""
    return event


def _normalize(token):
    return (token or "").strip().upper()


def _containment(token):
    if len(token) < ambiguity.MIN_CONTAINMENT_LEN or token in ambiguity.AMBIGUOUS_BARE:
        return None
    for canonical, ticker in issuers.ISSUER_TICKERS.items():
        if token != canonical and (token in canonical or canonical in token):
            return ticker
    return None


def _fuzzy(token):
    universe = list(issuers.ISSUER_TICKERS)
    best = difflib.get_close_matches(token, universe, n=1, cutoff=_FUZZY_FLOOR)
    return issuers.ISSUER_TICKERS[best[0]] if best else None


def resolve_ticker(issuer):
    """Resolve one issuer token through the ladder; None when unresolved."""
    token = _normalize(issuer)
    if not token:
        return None, "empty"
    if token in issuers.ISSUER_TICKERS:
        return issuers.ISSUER_TICKERS[token], "exact"
    if token in issuers.ALIASES:
        return issuers.ISSUER_TICKERS.get(issuers.ALIASES[token]), "alias"
    contained = _containment(token)
    if contained:
        return contained, "containment"
    fuzzed = _fuzzy(token)
    if fuzzed:
        return fuzzed, "fuzzy"
    parent = issuers.PARENTS.get(token)
    if parent:
        ticker = issuers.ISSUER_TICKERS.get(parent)
        if ticker:
            return ticker, "parent"
    return None, "unresolved"


def build_exposure(table):
    """Rebuild exposure rows from the events table (positional row reads)."""
    exposure = []
    for row in table:
        issuer = row[4]
        ticker, method = resolve_ticker(issuer)
        exposure.append({
            "symbol": row[2],
            "kind": row[3],
            "issuer": issuer,
            "ticker": ticker,
            "method": method,
            "venue": row[5],
            "source": row[6],
            "as_of": row[0],
        })
    return exposure


def explain(issuer):
    """Provenance record for one resolution (desks use this in escalations)."""
    ticker, method = resolve_ticker(issuer)
    return {
        "input": issuer,
        "normalized": _normalize(issuer),
        "ticker": ticker,
        "method": method,
        "limitations": (
            "containment gated by reference/ambiguity.AMBIGUOUS_BARE and the "
            "length floor; fuzzy floor %.2f; unresolved stays in the venue bucket"
            % _FUZZY_FLOOR),
    }
