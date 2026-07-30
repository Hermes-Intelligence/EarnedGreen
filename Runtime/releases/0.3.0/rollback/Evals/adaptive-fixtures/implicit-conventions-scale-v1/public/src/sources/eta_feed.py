"""Eta Stock Exchange feed: scrape capture only - parser not built.

The eta notice board is fetched hourly by the ops runner (the request
descriptor below is what the runner executes); the raw rss payload lands in
the raw archive (see data/raw/index.json for the capture history). load_events
stays unimplemented until the parser is specified against a reviewed capture;
do NOT register eta in the pipeline until then (see the pipeline registry
docstring).

Capture status: raw archive only. Parser status: not started.
"""

ETA_BASE_URL = "https://eta-se.example/market-notices.rss"

FETCH_HEADERS = {
    "User-Agent": "wire-platform/2.4 (+ops@wire.example)",
    "Accept": "application/rss+xml",
    "Accept-Language": "en",
}

# Capture-review dossier (EU desk):
CAPTURE_NOTES = {
    "region": "EU",
    "format": "rss",
    "cadence": "hourly",
    "auth": "none",
    "pagination": "single page",
    "observed_fields": ('title', 'guid', 'pubDate', 'description'),
    "known_issues": (
        "halts and resumptions share one RSS category; kind must be parsed out of the title text",
    ),
}


def fetch_notices(session=None):
    """Build the request descriptor the ops runner executes for eta.

    This module never performs network I/O itself; the runner does, and the
    payload is archived before any parsing would happen.
    """
    return {
        "method": "GET",
        "url": ETA_BASE_URL,
        "headers": dict(FETCH_HEADERS),
        "archive_as": "raw/eta/{date}.rss",
    }


def load_events(payload):
    raise NotImplementedError(
        "eta parser not implemented; scrape capture only (see module docstring)")


def ingest(payload, table, log):
    raise NotImplementedError(
        "eta parser not implemented; scrape capture only (see module docstring)")

# Capture excerpt (2026-06-30):
#   <item><title>Trading halt: PLT</title><guid>eta-2026-88121</guid>
#         <pubDate>Tue, 30 Jun 2026 06:00:00 GMT</pubDate></item>
