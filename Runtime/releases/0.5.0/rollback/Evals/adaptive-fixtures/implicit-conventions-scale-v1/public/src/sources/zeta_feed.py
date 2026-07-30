"""Zeta Exchange feed: scrape capture only - parser not built.

The zeta notice board is fetched daily 07:00 CET by the ops runner (the request
descriptor below is what the runner executes); the raw html payload lands in
the raw archive (see data/raw/index.json for the capture history). load_events
stays unimplemented until the parser is specified against a reviewed capture;
do NOT register zeta in the pipeline until then (see the pipeline registry
docstring).

Capture status: raw archive only. Parser status: not started.
"""

ZETA_BASE_URL = "https://www.zeta-exchange.example/notices/today"

FETCH_HEADERS = {
    "User-Agent": "wire-platform/2.4 (+ops@wire.example)",
    "Accept": "text/html",
    "Accept-Language": "en",
}

# Capture-review dossier (EU desk):
CAPTURE_NOTES = {
    "region": "EU",
    "format": "html",
    "cadence": "daily 07:00 CET",
    "auth": "none",
    "pagination": "single page",
    "observed_fields": ('instrument', 'category', 'headline', 'date'),
    "known_issues": (
        "the single 'date' column is ambiguous: capture review has not yet established whether it is the published or the effective date",
    ),
}


def fetch_notices(session=None):
    """Build the request descriptor the ops runner executes for zeta.

    This module never performs network I/O itself; the runner does, and the
    payload is archived before any parsing would happen.
    """
    return {
        "method": "GET",
        "url": ZETA_BASE_URL,
        "headers": dict(FETCH_HEADERS),
        "archive_as": "raw/zeta/{date}.html",
    }


def load_events(payload):
    raise NotImplementedError(
        "zeta parser not implemented; scrape capture only (see module docstring)")


def ingest(payload, table, log):
    raise NotImplementedError(
        "zeta parser not implemented; scrape capture only (see module docstring)")

# Capture excerpt (2026-06-30):
#   <li class="notice"><span>KLR</span><em>Suspension</em><time>2026-06-30</time></li>
#   <li class="notice"><span>VNTA</span><em>Neuzulassung</em><time>2026-06-30</time></li>
