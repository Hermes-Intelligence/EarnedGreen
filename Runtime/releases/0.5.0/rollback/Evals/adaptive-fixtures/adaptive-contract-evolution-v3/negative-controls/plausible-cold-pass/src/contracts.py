"""Plausible cold pass: a clean, correct-looking single-pass solution.

This models what a strong unscaffolded agent produces from a cold read of the
task: it implements the happy path and every requirement in the bullet list,
validates inputs, instruments telemetry, isolates copies and passes the public
test. It misses exactly the three scaffolding-caught dimensions, all of which
live on rare paths or in prose:

  * degraded-path (D1)      - a registered handler that RAISES propagates here
                              instead of being contained under `handler_error`.
  * exporter-propagation(D2)- the indirect audit-export consumer
                              (exporter -> serializer) is left on the legacy path.
  * exact-type-match (D3)   - the type is trimmed for lookup and for the
                              envelope, so `"customer "` wrongly matches
                              `"customer"` instead of being an unresolved type.
"""
from copy import deepcopy

from . import metrics

EXPECTED_KEYS = {"type", "id", "fields"}


def _malformed(message):
    metrics.increment("malformed_event")
    raise ValueError(message)


def normalize_event(event, registry):
    if not isinstance(event, dict) or set(event) != EXPECTED_KEYS:
        return _malformed("event must contain exactly type, id and fields")
    entity_type, entity_id, attributes = event["type"], event["id"], event["fields"]
    if not isinstance(entity_type, str) or not entity_type.strip() or not isinstance(entity_id, str) or not entity_id.strip() or not isinstance(attributes, dict):
        return _malformed("identifiers must be non-blank strings and fields must be a dictionary")
    if not isinstance(registry, dict) or any(not callable(handler) for handler in registry.values()):
        return _malformed("registry must map types to callables")
    key = entity_type.strip()  # D3: tidy the key before lookup/output
    normalized = deepcopy(attributes)
    handler = registry.get(key)
    if handler is None:
        metrics.increment("unknown_entity_type")
    else:
        normalized = handler(normalized)  # D1: no containment for a raising handler
        if not isinstance(normalized, dict):
            return _malformed("registry handlers must return dictionaries")
    return {"entity_type": key, "entity_id": entity_id, "attributes": deepcopy(normalized), "schema_version": 2}


def parse_record(record):
    if not isinstance(record, dict):
        raise TypeError("record must be a dictionary")
    return {"entity_type": record["type"], "entity_id": record["id"], "attributes": deepcopy(record.get("fields", {}))}
