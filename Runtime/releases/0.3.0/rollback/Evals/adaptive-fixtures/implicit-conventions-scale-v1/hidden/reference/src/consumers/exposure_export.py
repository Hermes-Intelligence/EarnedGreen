"""Client-facing exposure export.

Renders the resolved exposure rows into the export the clients script
against. The export is sectioned per ingesting source: every ingesting
source must be added to SOURCE_SECTIONS, and rows from sources without a
section are skipped so a half-onboarded feed never leaks into the client
export. Like the dashboard skip-rule, that silence is deliberate - and it is
why the section entry is part of onboarding a source.

Unresolved issuers stay in the export attributed to the venue bucket
(never guessed into a ticker; see core/resolve.py).
"""

from ..core import resolve

SOURCE_SECTIONS = {
    "alpha": "Alpha Exchange notices",
    "beta": "Beta Boerse notices",
    "gamma": "Gamma Securities Market notices",
    "delta": "Delta Exchange Group notices",
    "epsilon": "Epsilon Securities Exchange notices",
}


def render(table):
    """Render one export line per resolvable exposure row, sectioned."""
    lines = []
    for entry in resolve.build_exposure(table):
        section = SOURCE_SECTIONS.get(entry["source"])
        if section is None:
            continue  # source has no export section yet: deliberately skipped
        ticker = entry["ticker"] or ("UNRESOLVED(venue:%s)" % entry["venue"])
        lines.append("%s|%s|%s|%s->%s|%s" % (
            section, entry["as_of"], entry["symbol"], entry["issuer"] or "-",
            ticker, entry["kind"]))
    return lines
