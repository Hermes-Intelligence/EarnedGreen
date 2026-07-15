"""Shared per-record house flow (v2) and the migration state of the sources.

The house flow for every record, in this exact order:

    as_of from dates.as_of_date (published, never effective)
    -> guard.scrub_tokens
    -> resolve.resolve_issuer

house_flow() runs those three steps and counts the pass in FLOW_COUNTS, keyed
by source code. The counter is how consumers/run_health.py verifies a source
actually used the shared layer instead of hand-rolling its own flow.

MIGRATION: gamma and delta are migrated to house_flow. alpha and beta still
carry the same steps inline and are grandfathered in
run_health._LEGACY_SOURCES until their migration lands. Every NEW source
starts on house_flow; never copy the inline flow out of alpha_feed or
beta_feed into new code - the inline copies are scheduled for deletion.
"""

from . import dates, guard, resolve

FLOW_COUNTS = {}


def house_flow(event, source):
    """Run the shared per-record flow and count the pass for run_health."""
    event["as_of"] = dates.as_of_date(event)
    guard.scrub_tokens(event)
    resolve.resolve_issuer(event)
    FLOW_COUNTS[source] = FLOW_COUNTS.get(source, 0) + 1
    return event


def reset_counts():
    """Test/maintenance helper: forget all per-source flow counts."""
    FLOW_COUNTS.clear()
