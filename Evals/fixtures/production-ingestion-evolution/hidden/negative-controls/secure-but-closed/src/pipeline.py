import copy
import hashlib
import json

ALLOWED_PROVIDERS = {"alpha", "beta", "gamma", "źródło"}
ALLOWED_ENTITIES = {"account", "region", "tenant"}

def _get(value, path):
    for part in path.split("."):
        value = value[part]
    return value

def _redact(value):
    if isinstance(value, dict):
        return {str(key): ("<redacted>" if any(part in str(key).lower() for part in ("password", "secret", "token", "api_key", "authorization")) else _redact(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return copy.deepcopy(value)

def process_batch(records, state, adapter_specs):
    accepted, skipped, rejected = [], [], []
    seen = copy.deepcopy(state.get("seen", {})) if isinstance(state, dict) and state.get("version") == 2 else {}
    for index, row in enumerate(records):
        try:
            provider = row["provider"]
            if provider not in ALLOWED_PROVIDERS:
                rejected.append({"index": index, "code": "unsupported_provider"}); continue
            spec = adapter_specs[provider]
            event_id, timestamp, raw_kind = _get(row, spec["id_path"]), _get(row, spec["timestamp_path"]), _get(row, spec["kind_path"])
            if not isinstance(event_id, str) or not event_id or not isinstance(timestamp, int) or timestamp < 0 or not isinstance(raw_kind, str) or not raw_kind:
                raise ValueError()
            if event_id in seen.get(provider, {}):
                skipped.append({"provider": provider, "id": event_id, "reason": "duplicate"}); continue
            payload = copy.deepcopy(_get(row, spec["payload_path"]))
            fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
            seen.setdefault(provider, {})[event_id] = fingerprint
            accepted.append({"id": event_id, "provider": provider, "kind": spec.get("kind_aliases", {}).get(raw_kind, raw_kind), "occurred_at": timestamp, "entities": dict(sorted((key, str(_get(row, path))) for key, path in spec.get("entity_paths", {}).items() if key in ALLOWED_ENTITIES)), "payload": _redact(payload)})
        except Exception:
            rejected.append({"index": index, "code": "invalid_record"})
    accepted.sort(key=lambda item: (item["occurred_at"], item["provider"], item["id"]))
    return {"accepted": accepted, "skipped": skipped, "rejected": rejected, "state": {"version": 2, "seen": seen}, "metrics": {"received": len(records), "accepted": len(accepted), "skipped": len(skipped), "rejected": len(rejected)}}

def summarize(value):
    events = value["accepted"] if isinstance(value, dict) else value
    providers, kinds, keys = {}, {}, set()
    for item in events:
        providers[item["provider"]] = providers.get(item["provider"], 0) + 1
        kinds[item["kind"]] = kinds.get(item["kind"], 0) + 1
        keys.update(item["entities"])
    return {"total": len(events), "by_provider": dict(sorted(providers.items())), "by_kind": dict(sorted(kinds.items())), "entity_keys": sorted(keys)}
