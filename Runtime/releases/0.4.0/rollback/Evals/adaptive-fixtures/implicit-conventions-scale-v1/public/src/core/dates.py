"""Point-in-time date discipline.

Every event carries two dates: published_at (when the venue made the event
public) and effective_at (when the action takes effect on the venue). The
events table is a point-in-time dataset: as_of must ALWAYS be the knowledge
date, published_at, never effective_at. Keying by effective_at introduces
look-ahead: a query for day D would surface events the market could not have
known on day D. Nothing crashes when you get this wrong; the data is just
quietly untrustworthy, and every backtest built on it is quietly wrong too.

The parse helpers below exist because venue feeds disagree about date
encodings (epoch milliseconds, US month-first strings); every source
normalizes to ISO date strings before anything downstream sees the event.
"""

from datetime import datetime, timezone


def as_of_date(event):
    """The date this event became knowable: always the published date."""
    return event["published_at"]


def epoch_ms_to_iso_date(value):
    """Convert an epoch-milliseconds timestamp to an ISO date string (UTC)."""
    if value in (None, "", 0):
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc).date().isoformat()
    except (ValueError, OverflowError, OSError):
        return None


def parse_mdy(value):
    """Parse a US MM/DD/YYYY (or MM-DD-YYYY) date string to ISO."""
    value = (value or "").strip()
    for fmt in ("%m/%d/%Y", "%m-%d-%Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def validate_iso(value):
    """True when value is a well-formed ISO date string (YYYY-MM-DD)."""
    try:
        datetime.strptime(value or "", "%Y-%m-%d")
    except (TypeError, ValueError):
        return False
    return True


def lead_days(event):
    """Publish-to-effect lead time in whole days (None when unparseable)."""
    if not (validate_iso(event.get("published_at")) and validate_iso(event.get("effective_at"))):
        return None
    published = datetime.strptime(event["published_at"], "%Y-%m-%d")
    effective = datetime.strptime(event["effective_at"], "%Y-%m-%d")
    return (effective - published).days
