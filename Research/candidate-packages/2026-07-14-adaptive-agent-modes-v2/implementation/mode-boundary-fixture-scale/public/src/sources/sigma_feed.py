"""Sigma National Market feed: scrape capture only - parser not built.

The sigma notice board is fetched daily 06:30 ET by the ops runner (the request
descriptor below is what the runner executes); the raw html payload lands in
the raw archive (see data/raw/index.json for the capture history). load_events
stays unimplemented until the parser is specified against a reviewed capture;
do NOT register sigma in the pipeline until then (see the pipeline registry
docstring).

Capture status: raw archive only. Parser status: not started.
"""

SIGMA_BASE_URL = "https://notices.sigma-market.example/api/daily"

FETCH_HEADERS = {
    "User-Agent": "wire-platform/2.4 (+ops@wire.example)",
    "Accept": "text/html",
    "Accept-Language": "en",
}

# Capture-review dossier (US desk):
CAPTURE_NOTES = {
    "region": "US",
    "format": "html",
    "cadence": "daily 06:30 ET",
    "auth": "none",
    "pagination": "single page",
    "observed_fields": ('sym', 'hdr', 'body', 'pub', 'eff'),
    "known_issues": (
        "pagination appears when > 40 notices in a day (never captured yet)",
        "the body column embeds HTML entities",
    ),
}


def fetch_notices(session=None):
    """Build the request descriptor the ops runner executes for sigma.

    This module never performs network I/O itself; the runner does, and the
    payload is archived before any parsing would happen.
    """
    return {
        "method": "GET",
        "url": SIGMA_BASE_URL,
        "headers": dict(FETCH_HEADERS),
        "archive_as": "raw/sigma/{date}.html",
    }


def load_events(payload):
    raise NotImplementedError(
        "sigma parser not implemented; scrape capture only (see module docstring)")


def ingest(payload, table, log):
    raise NotImplementedError(
        "sigma parser not implemented; scrape capture only (see module docstring)")


# --- DRAFT parser sketch (Phase 3, NOT wired) --------------------------------
# The sketch below is an aspirational draft kept for the Phase 3 kickoff.
# It has never run against a real capture and does not follow the current
# core contracts (dict rows, effective-date keying). Do not copy it.
#
# def _draft_parse(payload):
#     out = []
#     for block in payload.get("blocks", []):
#         out.append({
#             "symbol": block["sym"],
#             "kind": block["hdr"],
#             "date": block["eff"],          # DRAFT: keyed by effective date
#         })
#     return out

# Capture excerpt (2026-06-30, first 3 blocks of the HTML table):
#   <tr><td>WLTX</td><td>Halt</td><td>News pending</td><td>06/30/2026</td><td>07/01/2026</td></tr>
#   <tr><td>GRNW</td><td>Halt</td><td>Volatility</td><td>06/30/2026</td><td>06/30/2026</td></tr>
#   <tr><td>MRSH</td><td>Resume</td><td>Review complete</td><td>06/30/2026</td><td>06/30/2026</td></tr>
