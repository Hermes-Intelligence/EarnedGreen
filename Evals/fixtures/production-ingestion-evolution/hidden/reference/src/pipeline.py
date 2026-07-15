import copy
import hashlib
import json
from collections.abc import Mapping


SENSITIVE_FRAGMENTS = ("password", "secret", "token", "api_key", "authorization")


def _get(value, path):
    if not isinstance(path, str) or not path or path.startswith(".") or path.endswith("."):
        raise ValueError("invalid path")
    current = value
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            raise ValueError("missing path")
        current = current[part]
    return current


def _redact(value):
    if isinstance(value, Mapping):
        result = {}
        for key, item in value.items():
            key_text = str(key)
            lowered = key_text.lower()
            result[key_text] = "<redacted>" if any(fragment in lowered for fragment in SENSITIVE_FRAGMENTS) else _redact(item)
        return result
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, tuple):
        return [_redact(item) for item in value]
    return copy.deepcopy(value)


def _state_v2(state):
    if state is None:
        state = {}
    if not isinstance(state, Mapping):
        raise ValueError("invalid state")
    seen = {}
    if state.get("version") == 2:
        source = state.get("seen", {})
        if not isinstance(source, Mapping):
            raise ValueError("invalid state")
        for provider, identities in source.items():
            if not isinstance(provider, str) or not isinstance(identities, Mapping):
                raise ValueError("invalid state")
            seen[provider] = {str(identity): fingerprint for identity, fingerprint in identities.items()}
    else:
        legacy = state.get("seen_ids", [])
        if not isinstance(legacy, list):
            raise ValueError("invalid state")
        for identity in legacy:
            if not isinstance(identity, str) or ":" not in identity:
                raise ValueError("invalid state")
            provider, event_id = identity.split(":", 1)
            seen.setdefault(provider, {})[event_id] = None
    return seen


def _fingerprint(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _canonical(record, specs):
    if not isinstance(record, Mapping):
        raise ValueError("invalid_record")
    provider = record.get("provider")
    if not isinstance(provider, str) or not provider:
        raise ValueError("invalid_record")
    if provider not in specs:
        raise LookupError("unsupported_provider")
    spec = specs[provider]
    if not isinstance(spec, Mapping) or not isinstance(spec.get("entity_paths", {}), Mapping):
        raise TypeError("invalid_adapter")
    try:
        event_id = _get(record, spec["id_path"])
        occurred_at = _get(record, spec["timestamp_path"])
        raw_kind = _get(record, spec["kind_path"])
        raw_payload = copy.deepcopy(_get(record, spec["payload_path"]))
    except KeyError as exc:
        raise TypeError("invalid_adapter") from exc
    if not isinstance(event_id, str) or not event_id or not isinstance(raw_kind, str) or not raw_kind:
        raise ValueError("invalid_record")
    if isinstance(occurred_at, bool) or not isinstance(occurred_at, int) or occurred_at < 0:
        raise ValueError("invalid_record")
    aliases = spec.get("kind_aliases", {})
    if not isinstance(aliases, Mapping):
        raise TypeError("invalid_adapter")
    kind = aliases.get(raw_kind, raw_kind)
    if not isinstance(kind, str) or not kind:
        raise ValueError("invalid_record")
    entities = {}
    for key, path in spec.get("entity_paths", {}).items():
        if not isinstance(key, str) or not key:
            raise TypeError("invalid_adapter")
        value = _get(record, path)
        if value is None or isinstance(value, (Mapping, list, tuple, set)):
            raise ValueError("invalid_record")
        entities[key] = str(value)
    raw_event = {"id": event_id, "provider": provider, "kind": kind, "occurred_at": occurred_at, "entities": dict(sorted(entities.items())), "payload": raw_payload}
    returned = copy.deepcopy(raw_event)
    returned["payload"] = _redact(raw_payload)
    return returned, _fingerprint(raw_event)


def process_batch(records, state, adapter_specs):
    if not isinstance(records, (list, tuple)) or not isinstance(adapter_specs, Mapping):
        raise ValueError("invalid arguments")
    seen = _state_v2(copy.deepcopy(state))
    accepted, skipped, rejected = [], [], []
    for index, record in enumerate(records):
        try:
            event, fingerprint = _canonical(record, adapter_specs)
            provider, event_id = event["provider"], event["id"]
            previous = seen.get(provider, {}).get(event_id, "__missing__")
            if previous != "__missing__":
                if previous is None or previous == fingerprint:
                    skipped.append({"provider": provider, "id": event_id, "reason": "duplicate"})
                else:
                    rejected.append({"index": index, "code": "identity_conflict"})
                continue
            seen.setdefault(provider, {})[event_id] = fingerprint
            accepted.append(event)
        except LookupError:
            rejected.append({"index": index, "code": "unsupported_provider"})
        except TypeError:
            rejected.append({"index": index, "code": "invalid_adapter"})
        except Exception:
            rejected.append({"index": index, "code": "invalid_record"})
    accepted.sort(key=lambda event: (event["occurred_at"], event["provider"], event["id"]))
    normalized_seen = {provider: dict(sorted(identities.items())) for provider, identities in sorted(seen.items())}
    result = {"accepted": accepted, "skipped": skipped, "rejected": rejected, "state": {"version": 2, "seen": normalized_seen}}
    result["metrics"] = {"received": len(records), "accepted": len(accepted), "skipped": len(skipped), "rejected": len(rejected)}
    return result


def summarize(events_or_batch_result):
    events = events_or_batch_result.get("accepted") if isinstance(events_or_batch_result, Mapping) else events_or_batch_result
    if not isinstance(events, list):
        raise ValueError("events")
    by_provider, by_kind, entity_keys = {}, {}, set()
    for event in events:
        by_provider[event["provider"]] = by_provider.get(event["provider"], 0) + 1
        by_kind[event["kind"]] = by_kind.get(event["kind"], 0) + 1
        entity_keys.update(event.get("entities", {}))
    return {"total": len(events), "by_provider": dict(sorted(by_provider.items())), "by_kind": dict(sorted(by_kind.items())), "entity_keys": sorted(entity_keys)}
