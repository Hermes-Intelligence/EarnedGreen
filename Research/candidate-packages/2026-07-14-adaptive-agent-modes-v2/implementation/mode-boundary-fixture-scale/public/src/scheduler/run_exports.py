"""Exports stage: render the client-facing exports from today's tables.

Runs after resolution so the exposure export sees today's rebuilt exposure.
Export formats are owned by the consumer modules; this shell only wires the
day's state through them.
"""

from ..consumers import alerts, exposure_export


def run(state):
    state["exports"]["exposure"] = exposure_export.render(state["table"])
    state["exports"]["alerts"] = alerts.build_alerts(state["log"])
    return state
