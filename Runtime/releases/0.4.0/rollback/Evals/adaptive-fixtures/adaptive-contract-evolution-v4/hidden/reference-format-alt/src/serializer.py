from .contracts import normalize_event


def serialize(event, registry):
    # Deliberately different audit-line format from hidden/reference
    # (`3:customer:1:['n']`) and from the live arms (`customer:1:['n']:3`,
    # `customer:1:v3:['n']`): `@`-joined identity, labelled key list, trailing
    # `schema=` version. Same SUBSTANCE, different serialization.
    parsed = normalize_event(event, registry)
    keys = ",".join(sorted(parsed["attributes"]))
    return f"{parsed['entity_type']}@{parsed['entity_id']} keys=[{keys}] schema={parsed['schema_version']}"
