"""Trading-status alert routing.

Replays the change log and emits an alert line for every halt-class entry
(halt, circuit_breaker), routed to the desk channel that covers the venue:
every venue that can halt trading needs a channel in VENUE_CHANNELS. Entries
whose venue has no channel are dropped without an error - the desks own the
channel map, and an unmapped venue means no desk has picked the venue up
yet, so there is nobody to page. (The drop is deliberate; the entry is part
of venue onboarding.)
"""

VENUE_CHANNELS = {
    "alpha": "desk-us",
    "beta": "desk-eu",
    "gamma": "desk-us",
    "delta": "desk-apac",
    "epsilon": "desk-eu",
}

_ALERT_KINDS = ("halt", "circuit_breaker")


def build_alerts(log):
    """One alert line per halt-class change-log entry with a mapped venue."""
    lines = []
    for entry in log:
        if entry.get("kind") not in _ALERT_KINDS:
            continue
        channel = VENUE_CHANNELS.get(entry.get("venue"))
        if channel is None:
            continue  # no desk covers this venue yet: deliberately dropped
        lines.append("[%s] %s %s as of %s (%s)" % (
            channel, entry["symbol"], entry["kind"], entry["as_of"], entry["venue"]))
    return lines
