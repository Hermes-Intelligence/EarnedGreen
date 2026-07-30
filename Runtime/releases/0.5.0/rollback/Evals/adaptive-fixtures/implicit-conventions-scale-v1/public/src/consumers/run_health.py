"""Run-health cross-check: did every source actually use the shared flow?

Counts loaded rows per source (positional read of the source column) and
compares against core/normalize.FLOW_COUNTS. sources still on the legacy
inline path (alpha, beta) are grandfathered in _LEGACY_SOURCES; any OTHER
source that loaded rows without house_flow passes is flagged - it
hand-rolled its own per-record flow, which is exactly what the migration is
retiring (see the MIGRATION note in core/normalize.py).

Flags are returned, not raised: health is advisory, the audit stage decides
what blocks.
"""

from ..core import normalize

_LEGACY_SOURCES = frozenset({"alpha", "beta"})


def check(table, flow_counts=None):
    """Return one flag string per source that bypassed the shared flow."""
    flow = normalize.FLOW_COUNTS if flow_counts is None else flow_counts
    loaded = {}
    for row in table:
        loaded[row[6]] = loaded.get(row[6], 0) + 1
    flags = []
    for source in sorted(loaded):
        if source in _LEGACY_SOURCES:
            continue
        if flow.get(source, 0) < loaded[source]:
            flags.append(
                "%s loaded %d rows but recorded %d house_flow passes: the source "
                "bypassed the shared flow (core/normalize.py)"
                % (source, loaded[source], flow.get(source, 0)))
    return flags
