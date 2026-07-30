"""Per-symbol latest-state report (internal view).

Reads the events table POSITIONALLY against core/rows.EVENT_COLUMNS - this
consumer (like the saved client exports) is exactly why the column order is
load-bearing. The report keeps, per symbol, the latest event by knowledge
date and reports its kind.
"""

from ..core import rows


class ReportError(Exception):
    """Raised when the events table violates the row contract."""


def latest_by_symbol(table):
    """Map symbol -> the positionally-read latest event for that symbol."""
    latest = {}
    for row in table:
        if not isinstance(row, (tuple, list)):
            raise ReportError(
                "event rows are positional sequences in EVENT_COLUMNS order, got %s"
                % type(row).__name__)
        if len(row) != len(rows.EVENT_COLUMNS):
            raise ReportError(
                "row has %d cells, EVENT_COLUMNS defines %d"
                % (len(row), len(rows.EVENT_COLUMNS)))
        symbol, as_of = row[2], row[0]
        current = latest.get(symbol)
        if current is None or as_of >= current[0]:
            latest[symbol] = row
    return latest


def render(table):
    """One line per symbol: symbol, latest kind, knowledge date, venue."""
    lines = []
    for symbol in sorted(latest_by_symbol(table)):
        row = latest_by_symbol(table)[symbol]
        lines.append("%s %s as-of %s on %s" % (symbol, row[3], row[0], row[5]))
    return lines
