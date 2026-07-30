"""Mu Boersen feed: scrape capture only - parser not built.

The mu notice board is fetched daily 07:30 CET by the ops runner (the request
descriptor below is what the runner executes); the raw json payload lands in
the raw archive (see data/raw/index.json for the capture history). load_events
stays unimplemented until the parser is specified against a reviewed capture;
do NOT register mu in the pipeline until then (see the pipeline registry
docstring).

Capture status: raw archive only. Parser status: not started.
"""

MU_BASE_URL = "https://mu-boersen.example/api/notices?window=1d"

FETCH_HEADERS = {
    "User-Agent": "wire-platform/2.4 (+ops@wire.example)",
    "Accept": "application/json",
    "Accept-Language": "en",
}

# Capture-review dossier (EU desk):
CAPTURE_NOTES = {
    "region": "EU",
    "format": "json",
    "cadence": "daily 07:30 CET",
    "auth": "none",
    "pagination": "single page",
    "observed_fields": ('isin', 'kind', 'text', 'published', 'validFrom'),
    "known_issues": (
        "notices are keyed by ISIN, not venue symbol; the symbology join is unresolved (see reference/symbology.py)",
    ),
}


def fetch_notices(session=None):
    """Build the request descriptor the ops runner executes for mu.

    This module never performs network I/O itself; the runner does, and the
    payload is archived before any parsing would happen.
    """
    return {
        "method": "GET",
        "url": MU_BASE_URL,
        "headers": dict(FETCH_HEADERS),
        "archive_as": "raw/mu/{date}.json",
    }


def load_events(payload):
    raise NotImplementedError(
        "mu parser not implemented; scrape capture only (see module docstring)")


def ingest(payload, table, log):
    raise NotImplementedError(
        "mu parser not implemented; scrape capture only (see module docstring)")

# Capture excerpt (2026-06-30):
#   {"isin": "DE000MUB0071", "kind": "halt", "text": "Handelsaussetzung",
#    "published": "2026-06-30", "validFrom": "2026-06-30"}
