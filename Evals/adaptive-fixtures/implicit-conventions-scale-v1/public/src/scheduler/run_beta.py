"""Daily shell for the beta feed.

Thin by design: fetch cadence and retries live with ops, ordering lives in
registry.RUN_ORDER (sources block, before run_resolution). The shell only
hands the day's raw payload to the pipeline dispatcher.
"""

from .. import pipeline


def run(state):
    payload = (state.get("raw") or {}).get("beta")
    if payload is None:
        return state  # no drop for this venue today
    pipeline.ingest("beta", payload, state["table"], state["log"])
    return state
