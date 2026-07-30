"""Iota Exchange feed: scrape capture only - parser not built.

The iota notice board is fetched daily 08:00 SGT by the ops runner (the request
descriptor below is what the runner executes); the raw html payload lands in
the raw archive (see data/raw/index.json for the capture history). load_events
stays unimplemented until the parser is specified against a reviewed capture;
do NOT register iota in the pipeline until then (see the pipeline registry
docstring).

Capture status: raw archive only. Parser status: not started.
"""

IOTA_BASE_URL = "https://iota-ex.example/announcements/trading-status"

FETCH_HEADERS = {
    "User-Agent": "wire-platform/2.4 (+ops@wire.example)",
    "Accept": "text/html",
    "Accept-Language": "en",
}

# Capture-review dossier (APAC desk):
CAPTURE_NOTES = {
    "region": "APAC",
    "format": "html",
    "cadence": "daily 08:00 SGT",
    "auth": "none",
    "pagination": "single page",
    "observed_fields": ('code', 'subject', 'announced', 'inforce'),
    "known_issues": (
        "subject lines are bilingual; only the English half is stable",
    ),
}


def fetch_notices(session=None):
    """Build the request descriptor the ops runner executes for iota.

    This module never performs network I/O itself; the runner does, and the
    payload is archived before any parsing would happen.
    """
    return {
        "method": "GET",
        "url": IOTA_BASE_URL,
        "headers": dict(FETCH_HEADERS),
        "archive_as": "raw/iota/{date}.html",
    }


def load_events(payload):
    raise NotImplementedError(
        "iota parser not implemented; scrape capture only (see module docstring)")


def ingest(payload, table, log):
    raise NotImplementedError(
        "iota parser not implemented; scrape capture only (see module docstring)")

# Capture excerpt (2026-06-30):
#   <div class="ann"><b>TRW</b> Trading Halt / (bilingual line omitted)
#        announced 2026-06-30 in force 2026-07-01</div>
