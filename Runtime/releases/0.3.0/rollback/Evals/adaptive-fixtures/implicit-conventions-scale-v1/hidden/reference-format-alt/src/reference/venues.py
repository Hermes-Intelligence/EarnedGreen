"""Venue registry: the golden copy of every venue the platform ingests.

Rule: every ingesting source must have a VENUES entry before its first
scheduled run. Downstream views join on this registry and silently skip
unknown venues (see consumers/venue_dashboard.py), so a missing entry does
not crash anything - the venue's events just never show up anywhere a human
looks. That silence is deliberate (half-configured venues must not leak into
client-facing views) and it is exactly why the entry is part of onboarding.

PLANNED lists roadmap venues that have a scraper capture but no parser; a
planned venue gets a VENUES entry when (and only when) its parser lands.
"""

VENUES = {
    "alpha": {
        "display": "Alpha Exchange",
        "country": "US",
        "tz": "America/New_York",
        "capabilities": ("halts", "resumptions", "listings"),
    },
    "beta": {
        "display": "Beta Boerse",
        "country": "DE",
        "tz": "Europe/Berlin",
        "capabilities": ("halts", "circuit_breakers", "listings", "delistings"),
    },
    "gamma": {
        "display": "Gamma Securities Market",
        "country": "US",
        "tz": "America/Chicago",
        "capabilities": ("halts", "resumptions"),
    },
    "delta": {
        "display": "Delta Exchange Group",
        "country": "JP",
        "tz": "Asia/Tokyo",
        "capabilities": ("halts", "resumptions", "delistings"),
    },
    "epsilon": {
        "display": "Epsilon Securities Exchange",
        "country": "IE",
        "tz": "Europe/Dublin",
        "capabilities": ("halts", "resumptions"),
    },
}

PLANNED = ("sigma", "zeta", "eta", "theta", "iota", "kappa", "mu", "nu", "xi", "omicron")
