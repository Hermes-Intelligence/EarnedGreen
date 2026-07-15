from .contracts import normalize_event


def digest_line(event, registry):
    # Deliberately different snapshot-line format from hidden/reference
    # (`v3|account|7|['m']`) and from the live arms (`account|7|['m']|3`,
    # `account|7|v3|['m']`): leading bracketed version, arrow-joined identity,
    # `::` before comma-joined bare keys. Same SUBSTANCE, different serialization.
    parsed = normalize_event(event, registry)
    keys = ",".join(sorted(parsed["attributes"]))
    return f"[{parsed['schema_version']}] {parsed['entity_type']} -> {parsed['entity_id']} :: {keys}"
