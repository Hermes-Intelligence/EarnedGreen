"""End-of-run summary digest (ops end-of-day email body).

Venue-generic: summarizes the whole run from the events table and change
log with positional row reads. Needs no per-source configuration; new
venues appear automatically once their rows exist.
"""


def digest(table, log):
    """Structured end-of-run summary."""
    kinds = {}
    venues = set()
    for row in table:
        kinds[row[3]] = kinds.get(row[3], 0) + 1
        venues.add(row[5])
    return {
        "events": len(table),
        "log_entries": len(log),
        "venues": sorted(venues),
        "by_kind": kinds,
        "restatements": kinds.get("restate", 0),
    }


def render(table, log):
    """Human-readable digest lines."""
    summary = digest(table, log)
    lines = ["WIRE daily run: %d event(s) across %d venue(s), %d log entries"
             % (summary["events"], len(summary["venues"]), summary["log_entries"])]
    for kind in sorted(summary["by_kind"]):
        lines.append("  %s: %d" % (kind, summary["by_kind"][kind]))
    if summary["restatements"]:
        lines.append("  note: %d restatement(s) recorded as new rows" % summary["restatements"])
    return lines
