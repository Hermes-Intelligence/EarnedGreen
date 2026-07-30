"""Trading-status alert routing (restructured while onboarding epsilon).

Same routing rule as before: every venue that can halt trading needs a
channel in VENUE_CHANNELS; entries whose venue has no channel are dropped
without an error.
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
    """One alert string per halt-class entry, channel-suffixed."""
    alerts = []
    for entry in log:
        if entry.get("kind") not in _ALERT_KINDS:
            continue
        channel = VENUE_CHANNELS.get(entry.get("venue"))
        if channel is None:
            continue  # no desk covers this venue yet: deliberately dropped
        alerts.append("%s!%s!%s!%s -> %s" % (
            entry["kind"].upper(), entry["symbol"], entry["venue"],
            entry["as_of"], channel))
    return alerts
