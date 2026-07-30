"""Xi Electronic Market feed: scrape capture only - parser not built.

The xi notice board is fetched hourly by the ops runner (the request
descriptor below is what the runner executes); the raw atom payload lands in
the raw archive (see data/raw/index.json for the capture history). load_events
stays unimplemented until the parser is specified against a reviewed capture;
do NOT register xi in the pipeline until then (see the pipeline registry
docstring).

Capture status: raw archive only. Parser status: not started.
"""

XI_BASE_URL = "https://xi-em.example/feeds/regulatory.atom"

FETCH_HEADERS = {
    "User-Agent": "wire-platform/2.4 (+ops@wire.example)",
    "Accept": "application/atom+xml",
    "Accept-Language": "en",
}

# Capture-review dossier (US desk):
CAPTURE_NOTES = {
    "region": "US",
    "format": "atom",
    "cadence": "hourly",
    "auth": "none",
    "pagination": "single page",
    "observed_fields": ('entry.title', 'entry.id', 'entry.updated', 'entry.summary'),
    "known_issues": (
        "entry.updated moves on every re-publication; a stable natural key has not been identified yet",
    ),
}


def fetch_notices(session=None):
    """Build the request descriptor the ops runner executes for xi.

    This module never performs network I/O itself; the runner does, and the
    payload is archived before any parsing would happen.
    """
    return {
        "method": "GET",
        "url": XI_BASE_URL,
        "headers": dict(FETCH_HEADERS),
        "archive_as": "raw/xi/{date}.atom",
    }


def load_events(payload):
    raise NotImplementedError(
        "xi parser not implemented; scrape capture only (see module docstring)")


def ingest(payload, table, log):
    raise NotImplementedError(
        "xi parser not implemented; scrape capture only (see module docstring)")

# Capture excerpt (2026-06-30):
#   <entry><title>Halt: VLX</title><id>urn:xi:notice:99182</id>
#          <updated>2026-06-30T11:20:41Z</updated></entry>
