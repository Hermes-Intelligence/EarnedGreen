"""Starter implementation with the production bug described in task.md."""

KNOWN_TYPES = {"person", "organization"}


def parse_entities(records):
    result = []
    seen = set()
    for record in records:
        if not isinstance(record, dict):
            continue
        name = record.get("name")
        entity_type = record.get("type")
        if not isinstance(name, str) or not isinstance(entity_type, str):
            continue
        name = name.strip()
        entity_type = entity_type.strip().lower()
        if not name or entity_type not in KNOWN_TYPES:
            continue
        key = (entity_type, name.lower())
        if key in seen:
            continue
        seen.add(key)
        result.append({"name": name, "type": entity_type})
    return result
