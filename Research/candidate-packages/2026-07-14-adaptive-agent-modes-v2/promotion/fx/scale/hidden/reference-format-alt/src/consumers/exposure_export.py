"""Client-facing exposure export (restructured while onboarding epsilon).

Same sectioning rule and skip-rule as before: every ingesting source must be
added to SOURCE_SECTIONS, and rows from sources without a section are
skipped so a half-onboarded feed never leaks into the client export.
Unresolved issuers stay attributed to the venue bucket.
"""

from ..core import resolve

SOURCE_SECTIONS = {
    "alpha": "Alpha Exchange notices",
    "beta": "Beta Boerse notices",
    "gamma": "Gamma Securities Market notices",
    "delta": "Delta Exchange Group notices",
    "epsilon": "Epsilon Securities Exchange notices",
}


def _format_line(section, entry):
    ticker = entry["ticker"] if entry["ticker"] else "UNRESOLVED venue=%s" % entry["venue"]
    return "%s :: %s => %s [%s] {%s @ %s}" % (
        entry["symbol"], entry["issuer"] or "-", ticker, section,
        entry["kind"], entry["as_of"])


def render(table):
    """Render the export as one newline-joined block, sectioned per source."""
    lines = []
    for entry in resolve.build_exposure(table):
        section = SOURCE_SECTIONS.get(entry["source"])
        if section is None:
            continue  # source has no export section yet: deliberately skipped
        lines.append(_format_line(section, entry))
    return "\n".join(lines)
