"""Run the whole daily schedule in RUN_ORDER."""

import importlib

from . import registry


def new_state(raw=None):
    """Fresh daily run state: raw payloads in, tables/exports out."""
    return {
        "raw": dict(raw or {}),
        "table": [],
        "log": [],
        "exposure": [],
        "exports": {},
        "audit": None,
        "health": [],
    }


def run_all(state=None):
    """Import and run every scheduled shell, strictly in RUN_ORDER."""
    state = new_state() if state is None else state
    for module_name in registry.RUN_ORDER:
        importlib.import_module(module_name).run(state)
    return state
