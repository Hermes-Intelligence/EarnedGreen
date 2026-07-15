"""Pipeline entry point: dispatch a raw source payload into the shared table."""

from .sources import alpha_feed, beta_feed, gamma_feed

SOURCES = {"alpha": alpha_feed, "beta": beta_feed, "gamma": gamma_feed}


def ingest(source, payload, table=None, log=None):
    table = [] if table is None else table
    log = [] if log is None else log
    return SOURCES[source].ingest(payload, table, log)
