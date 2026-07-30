"""Negative control: the reject-on-miss interpretation every paid solver chose.

Fully validated, instrumented and documented, but a valid event whose type has
no registry entry raises instead of passing through. Under the pinned v2 task
this is wrong and must be rejected by the hidden grader while passing the
public test.
"""
from copy import deepcopy

from . import metrics

EXPECTED_KEYS = {"type", "id", "fields"}


def _malformed(message):
    metrics.increment("malformed_event")
    raise ValueError(message)


def normalize_event(event, registry):
    if not isinstance(event, dict) or set(event) != EXPECTED_KEYS:
        _malformed("event must contain exactly type, id and fields")
    entity_type, entity_id, attributes = event["type"], event["id"], event["fields"]
    if not isinstance(entity_type, str) or not entity_type.strip() or not isinstance(entity_id, str) or not entity_id.strip() or not isinstance(attributes, dict):
        _malformed("identifiers must be non-blank strings and fields must be a dictionary")
    if not isinstance(registry, dict) or any(not callable(handler) for handler in registry.values()):
        _malformed("registry must map types to callables")
    handler = registry.get(entity_type)
    if handler is None:
        metrics.increment("unknown_entity_type")
        raise ValueError(f"unknown entity type: {entity_type}")
    normalized = handler(deepcopy(attributes))
    if not isinstance(normalized, dict):
        _malformed("registry handlers must return dictionaries")
    return {"entity_type": entity_type, "entity_id": entity_id, "attributes": deepcopy(normalized)}


def parse_record(record):
    if not isinstance(record, dict):
        raise TypeError("record must be a dictionary")
    return {"entity_type": record["type"], "entity_id": record["id"], "attributes": deepcopy(record.get("fields", {}))}
