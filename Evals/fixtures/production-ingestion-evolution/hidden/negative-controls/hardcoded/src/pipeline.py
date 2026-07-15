import copy

KNOWN_ENTITIES = ("account", "region", "tenant")

def _get(value, path):
    for part in path.split("."):
        value = value[part]
    return value

def process_batch(records, state, adapter_specs):
    accepted, rejected = [], []
    for index, row in enumerate(records):
        try:
            provider = row["provider"]
            if provider not in ("alpha", "beta"):
                raise ValueError()
            spec = adapter_specs[provider]
            raw_kind = _get(row, spec["kind_path"])
            accepted.append({"id": str(_get(row, spec["id_path"])), "provider": provider, "kind": spec.get("kind_aliases", {}).get(raw_kind, raw_kind), "occurred_at": int(_get(row, spec["timestamp_path"])), "entities": {key: str(_get(row, path)) for key, path in spec.get("entity_paths", {}).items() if key in KNOWN_ENTITIES}, "payload": copy.deepcopy(_get(row, spec["payload_path"]))})
        except Exception:
            rejected.append({"index": index, "code": "invalid_record"})
    accepted.sort(key=lambda item: (item["occurred_at"], item["provider"], item["id"]))
    return {"accepted": accepted, "skipped": [], "rejected": rejected, "state": {"version": 2, "seen": {}}, "metrics": {"received": len(records), "accepted": len(accepted), "skipped": 0, "rejected": len(rejected)}}

def summarize(value):
    events = value["accepted"] if isinstance(value, dict) else value
    providers, kinds, keys = {}, {}, set()
    for item in events:
        providers[item["provider"]] = providers.get(item["provider"], 0) + 1
        kinds[item["kind"]] = kinds.get(item["kind"], 0) + 1
        keys.update(item["entities"])
    return {"total": len(events), "by_provider": dict(sorted(providers.items())), "by_kind": dict(sorted(kinds.items())), "entity_keys": sorted(keys)}
