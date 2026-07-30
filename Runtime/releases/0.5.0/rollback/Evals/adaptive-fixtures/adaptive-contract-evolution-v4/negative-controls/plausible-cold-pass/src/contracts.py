"""Plausible cold pass: a clean, correct-looking single-pass solution.

This models what a strong unscaffolded agent produces from a cold read of the
task: it implements the happy path and every requirement in the bullet list,
validates inputs, instruments telemetry, isolates copies, matches types exactly,
contains raising handlers, and passes the public test. It misses exactly the
three scaffolding-caught dimensions, all of which live in prose and require
either tracing an indirect call chain or a re-run state interaction:

  * exporter-propagation (Chain A) - the indirect audit-export consumer
                              (exporter -> serializer) is left on the legacy path.
  * snapshot-propagation (Chain B) - the indirect cache-snapshot consumer
                              (snapshot -> digest_helper) is left on the legacy path.
  * repeat-dedup             - the unknown-type counter fires on every sighting;
                              a replayed unresolved identity is NOT deduplicated
                              into `unknown_repeat`.
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
    if (not isinstance(entity_type, str) or not entity_type.strip()
            or not isinstance(entity_id, str) or not entity_id.strip()
            or not isinstance(attributes, dict)):
        return _malformed("identifiers must be non-blank strings and fields must be a dictionary")
    if not isinstance(registry, dict) or any(not callable(handler) for handler in registry.values()):
        return _malformed("registry must map types to callables")
    handler = registry.get(entity_type)  # exact untrimmed match
    if handler is None:
        metrics.increment("unknown_entity_type")  # counts every sighting; no re-run dedup ledger
        normalized = deepcopy(attributes)
    else:
        try:
            normalized = handler(deepcopy(attributes))
        except Exception:
            metrics.increment("handler_error")
            normalized = deepcopy(attributes)
        else:
            if not isinstance(normalized, dict):
                return _malformed("registry handlers must return dictionaries")
    return {"entity_type": entity_type, "entity_id": entity_id, "attributes": deepcopy(normalized), "schema_version": 3}


def parse_record(record):
    if not isinstance(record, dict):
        raise TypeError("record must be a dictionary")
    return {"entity_type": record["type"], "entity_id": record["id"], "attributes": deepcopy(record.get("fields", {}))}
