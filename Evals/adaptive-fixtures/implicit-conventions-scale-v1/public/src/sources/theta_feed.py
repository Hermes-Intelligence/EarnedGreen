"""Theta Trading Venue feed: scrape capture only - parser not built.

The theta notice board is fetched daily 06:00 ET by the ops runner (the request
descriptor below is what the runner executes); the raw json payload lands in
the raw archive (see data/raw/index.json for the capture history). load_events
stays unimplemented until the parser is specified against a reviewed capture;
do NOT register theta in the pipeline until then (see the pipeline registry
docstring).

Capture status: raw archive only. Parser status: not started.
"""

THETA_BASE_URL = "https://api.theta-venue.example/v1/status-changes"

FETCH_HEADERS = {
    "User-Agent": "wire-platform/2.4 (+ops@wire.example)",
    "Accept": "application/json",
    "Accept-Language": "en",
}

# Capture-review dossier (US desk):
CAPTURE_NOTES = {
    "region": "US",
    "format": "json",
    "cadence": "daily 06:00 ET",
    "auth": "none",
    "pagination": "single page",
    "observed_fields": ('symbol', 'statusChange', 'effectiveTime', 'publishedTime', 'id'),
    "known_issues": (
        "timestamps are epoch milliseconds (see core/dates.epoch_ms_to_iso_date)",
    ),
}


def fetch_notices(session=None):
    """Build the request descriptor the ops runner executes for theta.

    This module never performs network I/O itself; the runner does, and the
    payload is archived before any parsing would happen.
    """
    return {
        "method": "GET",
        "url": THETA_BASE_URL,
        "headers": dict(FETCH_HEADERS),
        "archive_as": "raw/theta/{date}.json",
    }


def load_events(payload):
    raise NotImplementedError(
        "theta parser not implemented; scrape capture only (see module docstring)")


def ingest(payload, table, log):
    raise NotImplementedError(
        "theta parser not implemented; scrape capture only (see module docstring)")

# Capture excerpt (2026-06-30):
#   {"symbol": "DRV", "statusChange": "HALTED", "effectiveTime": 1782799200000,
#    "publishedTime": 1782795600000, "id": "THE-44107"}
