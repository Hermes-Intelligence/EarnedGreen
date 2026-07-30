"""Kappa Markets feed: scrape capture only - parser not built.

The kappa notice board is fetched daily 06:15 ET by the ops runner (the request
descriptor below is what the runner executes); the raw csv payload lands in
the raw archive (see data/raw/index.json for the capture history). load_events
stays unimplemented until the parser is specified against a reviewed capture;
do NOT register kappa in the pipeline until then (see the pipeline registry
docstring).

Capture status: raw archive only. Parser status: not started.
"""

KAPPA_BASE_URL = "https://kappa-markets.example/notices.csv"

FETCH_HEADERS = {
    "User-Agent": "wire-platform/2.4 (+ops@wire.example)",
    "Accept": "text/csv",
    "Accept-Language": "en",
}

# Capture-review dossier (US desk):
CAPTURE_NOTES = {
    "region": "US",
    "format": "csv",
    "cadence": "daily 06:15 ET",
    "auth": "none",
    "pagination": "single page",
    "observed_fields": ('SYMBOL', 'ACTION', 'NOTE', 'PUB_DT', 'EFF_DT', 'SEQ'),
    "known_issues": (
        "PUB_DT/EFF_DT arrive as MM/DD/YYYY (see core/dates.parse_mdy)",
    ),
}


def fetch_notices(session=None):
    """Build the request descriptor the ops runner executes for kappa.

    This module never performs network I/O itself; the runner does, and the
    payload is archived before any parsing would happen.
    """
    return {
        "method": "GET",
        "url": KAPPA_BASE_URL,
        "headers": dict(FETCH_HEADERS),
        "archive_as": "raw/kappa/{date}.csv",
    }


def load_events(payload):
    raise NotImplementedError(
        "kappa parser not implemented; scrape capture only (see module docstring)")


def ingest(payload, table, log):
    raise NotImplementedError(
        "kappa parser not implemented; scrape capture only (see module docstring)")

# Capture excerpt (2026-06-30):
#   SYMBOL,ACTION,NOTE,PUB_DT,EFF_DT,SEQ
#   HXM,HALT,News pending,06/30/2026,07/01/2026,1
#   JLT,RESUME,Review complete,06/30/2026,06/30/2026,2
