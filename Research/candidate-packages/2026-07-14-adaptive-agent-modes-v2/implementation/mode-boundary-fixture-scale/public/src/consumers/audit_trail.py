"""Compliance audit trail: replay and validate the change log.

The audit trail is the compliance record of everything the platform has
said; replay hard-fails on an unknown kind, a missing field or a gap in seq
(AuditError). The shape it enforces is the shape core/changelog.record
writes - the two files together ARE the change-log contract: the store
docstring states the discipline, this replay enforces it at the end of every
scheduled run (see scheduler/run_audit.py).
"""

from ..core import changelog

_REQUIRED_KEYS = ("seq", "event_id", "symbol", "kind", "as_of", "source", "venue")


class AuditError(Exception):
    """Raised when the change log violates the audit contract."""


def replay(log):
    """Validate every entry and return per-kind counts."""
    counts = {}
    expected_seq = 1
    for entry in log:
        for key in _REQUIRED_KEYS:
            if key not in entry:
                raise AuditError("change-log entry %r is missing %r" % (entry, key))
        if entry["seq"] != expected_seq:
            raise AuditError(
                "change-log seq gap: expected %d, got %r (append-only means no "
                "gaps and no rewrites)" % (expected_seq, entry["seq"]))
        if entry["kind"] not in changelog.KINDS:
            raise AuditError(
                "unknown kind %r: kinds are the closed vocabulary %r; a source "
                "must normalize venue-specific kinds before recording"
                % (entry["kind"], list(changelog.KINDS)))
        counts[entry["kind"]] = counts.get(entry["kind"], 0) + 1
        expected_seq += 1
    return counts
