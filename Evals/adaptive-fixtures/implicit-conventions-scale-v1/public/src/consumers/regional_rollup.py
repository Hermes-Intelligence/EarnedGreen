"""Regional event rollup (management weekly).

Groups venues into regions through the venue registry and counts events per
region. Venue-generic like latency_kpis: it consumes whatever the registry
knows; venues without a registry entry fall into the "unmapped" bucket
(counted, not shown per-venue - this is a management count, not a
client-facing view, so unmapped events must not vanish here).
"""

from ..reference import venues

_REGION_BY_COUNTRY = {
    "US": "Americas",
    "CA": "Americas",
    "DE": "EMEA",
    "IE": "EMEA",
    "NL": "EMEA",
    "GB": "EMEA",
    "JP": "APAC",
    "SG": "APAC",
    "AU": "APAC",
}


def rollup(table):
    """Map region -> event count (plus an 'unmapped' bucket)."""
    counts = {}
    for row in table:
        entry = venues.VENUES.get(row[5])
        if entry is None:
            region = "unmapped"
        else:
            region = _REGION_BY_COUNTRY.get(entry.get("country"), "other")
        counts[region] = counts.get(region, 0) + 1
    return counts


def render(table):
    """One line per region, unmapped last."""
    counts = rollup(table)
    ordered = sorted(counts, key=lambda region: (region == "unmapped", region))
    return ["%s: %d event(s)" % (region, counts[region]) for region in ordered]
