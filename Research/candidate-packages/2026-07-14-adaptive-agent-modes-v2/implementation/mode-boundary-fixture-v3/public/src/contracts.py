from copy import deepcopy


def parse_record(record):
    """Legacy record parser retained during the contract evolution."""
    return {"entity_type": record["type"], "entity_id": record["id"], "attributes": deepcopy(record.get("fields", {}))}


def normalize_event(event, registry):
    raise NotImplementedError("implement the evolved contract")
