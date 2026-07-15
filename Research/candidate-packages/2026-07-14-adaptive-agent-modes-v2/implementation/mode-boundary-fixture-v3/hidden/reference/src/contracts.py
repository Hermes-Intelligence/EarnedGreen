from copy import deepcopy

from . import metrics

EXPECTED_KEYS = {"type", "id", "fields"}
SCHEMA_VERSION = 2


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
    # Exact-match lookup: the blank check above used strip(), but the value used
    # for lookup and for the envelope is the original, untrimmed type string.
    handler = registry.get(entity_type)
    if handler is None:
        metrics.increment("unknown_entity_type")
        normalized = deepcopy(attributes)
    else:
        try:
            normalized = handler(deepcopy(attributes))
        except Exception:
            # Degraded fallback: a handler that raises is not a rejection.
            metrics.increment("handler_error")
            normalized = deepcopy(attributes)
        else:
            if not isinstance(normalized, dict):
                return _malformed("registry handlers must return dictionaries")
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "attributes": deepcopy(normalized),
        "schema_version": SCHEMA_VERSION,
    }


def parse_record(record):
    if not isinstance(record, dict):
        raise TypeError("record must be a dictionary")
    return {"entity_type": record["type"], "entity_id": record["id"], "attributes": deepcopy(record.get("fields", {}))}
