"""Nu Exchange feed: scrape capture only - parser not built.

The nu notice board is fetched daily 09:00 JST by the ops runner (the request
descriptor below is what the runner executes); the raw html payload lands in
the raw archive (see data/raw/index.json for the capture history). load_events
stays unimplemented until the parser is specified against a reviewed capture;
do NOT register nu in the pipeline until then (see the pipeline registry
docstring).

Capture status: raw archive only. Parser status: not started.
"""

NU_BASE_URL = "https://nu-exchange.example/en/trading-halts"

FETCH_HEADERS = {
    "User-Agent": "wire-platform/2.4 (+ops@wire.example)",
    "Accept": "text/html",
    "Accept-Language": "en",
}

# Capture-review dossier (APAC desk):
CAPTURE_NOTES = {
    "region": "APAC",
    "format": "html",
    "cadence": "daily 09:00 JST",
    "auth": "none",
    "pagination": "single page",
    "observed_fields": ('code', 'reason', 'halted_at', 'expected_resume'),
    "known_issues": (
        "the board only lists CURRENT halts; resumptions must be inferred by diffing consecutive captures",
    ),
}


def fetch_notices(session=None):
    """Build the request descriptor the ops runner executes for nu.

    This module never performs network I/O itself; the runner does, and the
    payload is archived before any parsing would happen.
    """
    return {
        "method": "GET",
        "url": NU_BASE_URL,
        "headers": dict(FETCH_HEADERS),
        "archive_as": "raw/nu/{date}.html",
    }


def load_events(payload):
    raise NotImplementedError(
        "nu parser not implemented; scrape capture only (see module docstring)")


def ingest(payload, table, log):
    raise NotImplementedError(
        "nu parser not implemented; scrape capture only (see module docstring)")

# Capture excerpt (2026-06-30, current-halts board):
#   <tr><td>OSR</td><td>Pending disclosure</td><td>2026-06-29 14:02</td><td>TBD</td></tr>
