from copy import deepcopy


def parse_record(record):
    return {"entity_type":record["type"],"entity_id":record["id"],"attributes":deepcopy(record.get("fields",{}))}


def normalize_event(event, registry):
    if not isinstance(event, dict):
        raise ValueError("event must be a dictionary")
    attributes = deepcopy(event.get("fields", {}))
    handler = registry.get(event["type"])
    if handler:
        attributes = handler(attributes)
    return {"entity_type":event["type"],"entity_id":event["id"],"attributes":deepcopy(attributes)}
