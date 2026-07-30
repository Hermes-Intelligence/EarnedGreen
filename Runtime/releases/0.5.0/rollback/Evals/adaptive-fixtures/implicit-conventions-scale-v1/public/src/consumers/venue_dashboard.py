"""Per-venue dashboard (the ops home screen).

Joins the events table against the venue registry
(reference/venues.py). By design, venues without a registry entry are
skipped - a half-configured venue must never leak into a client-facing
view, so an unregistered venue's events simply do not appear here. The
flip side: registering the venue IS part of onboarding a source, or the
venue's events never show up anywhere a human looks.
"""

from ..reference import calendars, venues


def render(table):
    """One line per registered venue with event and halt counts."""
    per_venue = {}
    for row in table:
        code = row[5]
        bucket = per_venue.setdefault(code, {"events": 0, "halts": 0, "dates": set()})
        bucket["events"] += 1
        if row[3] in ("halt", "circuit_breaker"):
            bucket["halts"] += 1
        bucket["dates"].add(row[0])
    lines = []
    for code in sorted(per_venue):
        entry = venues.VENUES.get(code)
        if entry is None:
            continue  # unregistered venue: deliberately not shown
        bucket = per_venue[code]
        holiday_note = ""
        for iso_date in sorted(bucket["dates"]):
            if calendars.is_holiday(code, iso_date):
                holiday_note = " (holiday session)"
                break
        lines.append("%s (%s): %d events, %d halted%s" % (
            entry["display"], code, bucket["events"], bucket["halts"], holiday_note))
    return lines
