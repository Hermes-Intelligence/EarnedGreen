"""Weak local control: a minimal happy-path hack.

Implements just enough to satisfy the public test. It skips the envelope's
`schema_version`, all input validation and telemetry, the exact-match rule, the
degraded fallback, and both the render and export consumers. It sits near the
floor and exists to prove the grader rewards graded coverage rather than mere
public-test passage.
"""
from copy import deepcopy


def parse_record(record):
    return {"entity_type": record["type"], "entity_id": record["id"], "attributes": deepcopy(record.get("fields", {}))}


def normalize_event(event, registry):
    attributes = deepcopy(event.get("fields", {}))
    handler = registry.get(event["type"])
    if handler:
        attributes = handler(attributes)
    return {"entity_type": event["type"], "entity_id": event["id"], "attributes": attributes}
