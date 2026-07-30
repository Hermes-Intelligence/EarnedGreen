"""Resolution stage: rebuild the exposure rows from the events table.

Runs AFTER the sources block: resolution rebuilds exposure from whatever the
source shells loaded in THIS run, so a source shell scheduled after
resolution contributes nothing to exposure until the next day - no error is
raised, the venue's exposure is just silently one day stale. That silent
degradation is why registry.RUN_ORDER keeps the whole sources block strictly
before this stage.

Idempotent and safe to re-run (full rebuild, no incremental state).
"""

from ..core import resolve


def run(state):
    state["exposure"] = resolve.build_exposure(state["table"])
    return state
