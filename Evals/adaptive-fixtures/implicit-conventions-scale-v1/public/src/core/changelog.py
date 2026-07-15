"""Append-only change log for the WIRE events platform.

House discipline, in force since the first client export shipped:

* The log is APPEND-ONLY: existing rows are never updated and never deleted.
  Consumers rebuild state by replaying the log, so rewriting history silently
  corrupts every point-in-time answer that has already been given out.
* A restatement (a feed re-issuing an earlier notice with corrected values)
  is recorded as a NEW row with kind="restate"; the original row stays.
* kinds are a CLOSED vocabulary (KINDS below). A source-specific kind must
  be normalized to this vocabulary before recording; the audit trail refuses
  to replay a log that contains anything else (see consumers/audit_trail.py).
* record() assigns the monotonically increasing seq. already_recorded() is
  the idempotency check every source runs before recording (core/identity.py
  documents what goes into the event_id state hash).
"""

KINDS = ("halt", "resume", "listing", "delisting", "circuit_breaker", "restate")


def record(log, event):
    """Append one change-log row. Never mutate rows already in the log."""
    log.append({
        "seq": len(log) + 1,
        "event_id": event.get("event_id", ""),
        "symbol": event["symbol"],
        "kind": event["kind"],
        "as_of": event["as_of"],
        "source": event.get("source", ""),
        "venue": event.get("venue", ""),
    })
    return log


def already_recorded(log, event_id):
    """True when this exact record STATE has been recorded before.

    This is the re-scrape idempotency check: an unchanged notice keeps its
    event_id and is skipped; a changed notice hashes to a new id and is
    recorded as a new row.
    """
    return any(entry.get("event_id") == event_id for entry in log)
