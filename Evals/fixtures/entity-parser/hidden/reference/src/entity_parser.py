def parse_entities(records):
    result, seen = [], set()
    if not isinstance(records, (list, tuple)):
        return result
    for record in records:
        if not isinstance(record, dict):
            continue
        name, kind = record.get("name"), record.get("type")
        if not isinstance(name, str) or not isinstance(kind, str):
            continue
        name, kind = name.strip(), kind.strip().casefold()
        if not name or not kind:
            continue
        key = (kind, name.casefold())
        if key in seen:
            continue
        seen.add(key); result.append({"name": name, "type": kind})
    return result
