"""Omicron Exchange feed: scrape capture only - parser not built.

The omicron notice board is fetched daily 07:45 CET by the ops runner (the request
descriptor below is what the runner executes); the raw html payload lands in
the raw archive (see data/raw/index.json for the capture history). load_events
stays unimplemented until the parser is specified against a reviewed capture;
do NOT register omicron in the pipeline until then (see the pipeline registry
docstring).

Capture status: raw archive only. Parser status: not started.
"""

OMICRON_BASE_URL = "https://omicron-ex.example/notice-board/current"

FETCH_HEADERS = {
    "User-Agent": "wire-platform/2.4 (+ops@wire.example)",
    "Accept": "text/html",
    "Accept-Language": "en",
}

# Capture-review dossier (EU desk):
CAPTURE_NOTES = {
    "region": "EU",
    "format": "html",
    "cadence": "daily 07:45 CET",
    "auth": "none",
    "pagination": "single page",
    "observed_fields": ('ticker', 'notice_type', 'notice_text', 'date_published', 'date_effective'),
    "known_issues": (
        "the notice board silently truncates notice_text at 140 characters",
    ),
}


def fetch_notices(session=None):
    """Build the request descriptor the ops runner executes for omicron.

    This module never performs network I/O itself; the runner does, and the
    payload is archived before any parsing would happen.
    """
    return {
        "method": "GET",
        "url": OMICRON_BASE_URL,
        "headers": dict(FETCH_HEADERS),
        "archive_as": "raw/omicron/{date}.html",
    }


def load_events(payload):
    raise NotImplementedError(
        "omicron parser not implemented; scrape capture only (see module docstring)")


def ingest(payload, table, log):
    raise NotImplementedError(
        "omicron parser not implemented; scrape capture only (see module docstring)")

# Capture excerpt (2026-06-30):
#   <div class="board-row"><span class="tkr">ZRC</span><span class="typ">Suspension</span>
#        <span class="txt">Suspension pending clarification of press reports concerning ...</span>
#        <span class="pub">2026-06-30</span><span class="eff">2026-07-01</span></div>
