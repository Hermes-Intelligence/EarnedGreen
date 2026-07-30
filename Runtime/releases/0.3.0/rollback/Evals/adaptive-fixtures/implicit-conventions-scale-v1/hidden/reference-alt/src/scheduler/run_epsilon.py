"""Daily shell for the epsilon feed (sources block, before resolution)."""

from .. import pipeline


def run(state):
    raw = state.get("raw") or {}
    if "epsilon" in raw:
        pipeline.ingest("epsilon", raw["epsilon"], state["table"], state["log"])
    return state
