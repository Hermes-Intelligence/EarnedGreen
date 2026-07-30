from copy import deepcopy

EXPECTED_KEYS={"type","id","fields"}


def normalize_event(event, registry):
    if not isinstance(event,dict) or set(event)!=EXPECTED_KEYS:
        raise ValueError("invalid event")
    entity_type,event_id,attributes=event["type"],event["id"],event["fields"]
    if not isinstance(entity_type,str) or not entity_type.strip() or not isinstance(event_id,str) or not event_id.strip() or not isinstance(attributes,dict):
        raise ValueError("invalid fields")
    if not isinstance(registry,dict) or any(not callable(value) for value in registry.values()):
        raise TypeError("invalid registry")
    copied=deepcopy(attributes); handler=registry.get(entity_type); normalized=handler(copied) if handler else copied
    if not isinstance(normalized,dict): raise TypeError("invalid handler result")
    return {"entity_type":entity_type,"entity_id":event_id,"attributes":deepcopy(normalized)}


def parse_record(record):
    return {"entity_type":record["type"],"entity_id":record["id"],"attributes":deepcopy(record.get("fields",{}))}
