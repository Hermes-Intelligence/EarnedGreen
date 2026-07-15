"""Audit stage: replay the change log and record run health.

Last in RUN_ORDER: the audit replay is the compliance record for the whole
run, and run_health cross-checks that every non-legacy source actually went
through the shared house flow (see consumers/run_health.py).
"""

from ..consumers import audit_trail, run_health


def run(state):
    state["audit"] = audit_trail.replay(state["log"])
    state["health"] = run_health.check(state["table"])
    return state
