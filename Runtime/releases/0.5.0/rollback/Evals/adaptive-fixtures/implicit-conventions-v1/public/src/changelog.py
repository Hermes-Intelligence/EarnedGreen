"""Append-only event change log.

House discipline: the log is APPEND-ONLY. A restatement (a feed re-issuing an
event for the same symbol with corrected values) is recorded as a NEW row with
kind="restate"; existing rows are never updated and never deleted. Consumers
rebuild current state by replaying the log, so rewriting history silently
corrupts every point-in-time query that has already been answered.
"""


def record(log, event):
    """Append one change-log row. Never mutate rows that are already in the log."""
    log.append({"symbol": event["symbol"], "kind": event["kind"], "as_of": event["as_of"]})
    return log
