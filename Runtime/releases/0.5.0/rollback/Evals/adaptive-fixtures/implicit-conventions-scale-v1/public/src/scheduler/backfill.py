"""Disaster-recovery backfill (manual, ops-run; NOT part of RUN_ORDER).

Rebuilds the events table and change log from archived raw payloads after a
store corruption. This is the ONLY sanctioned caller of the pipeline's
rebuild=True switch: scheduled ingestion never rebuilds, because the change
log is append-only and consumers replay it (see core/changelog.py). Running
a backfill invalidates every point-in-time answer already given out, which
is why it requires an ops incident ticket.
"""

from .. import pipeline


def backfill(archived_payloads, incident_ticket):
    """Rebuild the store from an ordered {source: payload} archive map."""
    if not incident_ticket:
        raise ValueError("backfill requires an ops incident ticket reference")
    table, log = [], []
    first = True
    for source, payload in archived_payloads.items():
        pipeline.ingest(source, payload, table, log, rebuild=first)
        first = False
    return table, log
