"""Ingestion dispatch for the WIRE events platform.

Only sources with a working parser are registered here; scrape-only stubs
stay unregistered until their parser lands. The registry key doubles as the
source code stamped on every row, and the scheduler shells call back into
this dispatcher, so key names must match the venue codes in
reference/venues.py.

rebuild=True truncates the events table and change log before loading. It is
a disaster-recovery tool for a corrupted store, never part of scheduled
ingestion: the change log is append-only precisely so history survives (see
core/changelog.py).
"""

from .sources import alpha_feed, beta_feed, delta_feed, gamma_feed

SOURCES = {
    "alpha": alpha_feed,
    "beta": beta_feed,
    "gamma": gamma_feed,
    "delta": delta_feed,
}


def ingest(source, payload, table=None, log=None, rebuild=False):
    """Dispatch one raw payload to its source parser."""
    table = [] if table is None else table
    log = [] if log is None else log
    if rebuild:
        del table[:]
        del log[:]
    return SOURCES[source].ingest(payload, table, log)
