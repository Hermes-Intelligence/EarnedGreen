"""Alternative reference: authored from the public task text alone, then reconciled.

The first draft of this module chose the other defensible interpretation at
every decision point (reject on registry miss, trust handler results verbatim,
count telemetry only for structural malformation, protect only the input from
mutation). It failed the hidden grader at 50/100, which proved the original
task text was ambiguous. task.md v2 now pins each of those decisions
explicitly; this module implements the pinned semantics with a rule-table
style that is deliberately different from the primary reference.
"""
from copy import deepcopy

from . import metrics

_SHAPE_RULES = (
    (lambda event: isinstance(event, dict), "event is not a mapping"),
    (lambda event: set(event) == {"type", "id", "fields"}, "event keys must be exactly type, id and fields"),
    (lambda event: isinstance(event["type"], str) and bool(event["type"].strip()), "type must be a non-blank string"),
    (lambda event: isinstance(event["id"], str) and bool(event["id"].strip()), "id must be a non-blank string"),
    (lambda event: isinstance(event["fields"], dict), "fields must be a dictionary"),
)


def _malformed(reason):
    metrics.increment("malformed_event")
    raise ValueError(reason)


def normalize_event(event, registry):
    for rule, reason in _SHAPE_RULES:
        try:
            valid = rule(event)
        except (TypeError, KeyError):
            valid = False
        if not valid:
            _malformed(reason)
    if not isinstance(registry, dict) or not all(callable(entry) for entry in registry.values()):
        _malformed("registry entries must be callables")
    kind, identity = event["type"], event["id"]
    attributes = deepcopy(event["fields"])
    if kind in registry:
        attributes = registry[kind](attributes)
        if not isinstance(attributes, dict):
            _malformed("handler results must be dictionaries")
    else:
        metrics.increment("unknown_entity_type")
    return {"entity_type": kind, "entity_id": identity, "attributes": deepcopy(attributes)}


def parse_record(record):
    if not isinstance(record, dict):
        raise TypeError("record must be a dictionary")
    return {"entity_type": record["type"], "entity_id": record["id"], "attributes": deepcopy(record.get("fields", {}))}
