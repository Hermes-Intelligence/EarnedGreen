import copy


KNOWN_ENTITIES = ("account", "region")


def _get(record, path):
    current = record
    for part in path.split("."):
        current = current[part]
    return current


def process_batch(records, state, adapter_specs):
    """Sample-driven starter: handles the public Alpha example only."""
    accepted = []
    rejected = []
    for index, record in enumerate(records):
        try:
            spec = adapter_specs[record["provider"]]
            payload = copy.deepcopy(_get(record, spec["payload_path"]))
            raw_kind = _get(record, spec["kind_path"])
            event = {
                "id": str(_get(record, spec["id_path"])),
                "provider": record["provider"],
                "kind": spec.get("kind_aliases", {}).get(raw_kind, raw_kind),
                "occurred_at": int(_get(record, spec["timestamp_path"])),
                "entities": {
                    name: str(_get(record, spec["entity_paths"][name]))
                    for name in KNOWN_ENTITIES
                    if name in spec.get("entity_paths", {})
                },
                "payload": payload,
            }
            accepted.append(event)
        except Exception:
            rejected.append({"index": index, "code": "invalid_record"})
    accepted.sort(key=lambda event: (event["occurred_at"], event["provider"], event["id"]))
    return {
        "accepted": accepted,
        "skipped": [],
        "rejected": rejected,
        "state": {"version": 2, "seen": {}},
        "metrics": {"received": len(records), "accepted": len(accepted), "skipped": 0, "rejected": len(rejected)},
    }


def summarize(events_or_batch_result):
    events = events_or_batch_result["accepted"] if isinstance(events_or_batch_result, dict) else events_or_batch_result
    by_provider = {}
    by_kind = {}
    entity_keys = set()
    for event in events:
        by_provider[event["provider"]] = by_provider.get(event["provider"], 0) + 1
        by_kind[event["kind"]] = by_kind.get(event["kind"], 0) + 1
        entity_keys.update(event["entities"])
    return {"total": len(events), "by_provider": dict(sorted(by_provider.items())), "by_kind": dict(sorted(by_kind.items())), "entity_keys": sorted(entity_keys)}
