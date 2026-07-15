"""Notice-latency KPIs (ops weekly review).

Measures, per venue, how far ahead of effect the venue publishes
(effective_at minus published_at in days, positional row reads). This
consumer is venue-generic: it iterates whatever venues appear in the events
table and needs no per-source configuration.
"""

from datetime import date


def _days_between(published, effective):
    try:
        p = date.fromisoformat(published)
        e = date.fromisoformat(effective)
    except (TypeError, ValueError):
        return None
    return (e - p).days


def lead_time_by_venue(table):
    """Map venue -> average publish-to-effect lead time in days."""
    sums = {}
    for row in table:
        lead = _days_between(row[8], row[9])
        if lead is None:
            continue
        bucket = sums.setdefault(row[5], [0, 0])
        bucket[0] += lead
        bucket[1] += 1
    return {venue: round(total / count, 2)
            for venue, (total, count) in sums.items() if count}


def render(table):
    """One line per venue with the average lead time."""
    leads = lead_time_by_venue(table)
    return ["%s: %.2f day(s) publish-to-effect lead" % (venue, leads[venue])
            for venue in sorted(leads)]
