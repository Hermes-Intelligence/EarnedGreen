import copy

SENSITIVE = {"secret", "token", "password", "api_key"}


def clean(value):
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items() if str(k).casefold() not in SENSITIVE}
    if isinstance(value, list):
        return [clean(v) for v in value]
    return copy.deepcopy(value)


def build_policy(request):
    if not isinstance(request, dict): raise ValueError("request")
    name = request.get("name")
    if not isinstance(name, str) or not name.strip(): raise ValueError("name")
    targets = request.get("targets")
    if not isinstance(targets, list) or not targets: raise ValueError("targets")
    output_targets, seen = [], set()
    for item in targets:
        if not isinstance(item, dict): raise ValueError("target")
        kind, value = item.get("type"), item.get("value")
        if not isinstance(kind, str) or not kind.strip() or not isinstance(value, str) or not value.strip(): raise ValueError("target")
        kind, value = kind.strip().casefold(), value.strip()
        key = (kind, value.casefold())
        if key not in seen: seen.add(key); output_targets.append({"type": kind, "value": value})
    timeout = request.get("timeout_seconds", 30); retries = request.get("retries", 2); dry = request.get("dry_run", True); metadata = request.get("metadata", {})
    if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= 300: raise ValueError("timeout")
    if isinstance(retries, bool) or not isinstance(retries, int) or not 0 <= retries <= 5: raise ValueError("retries")
    if not isinstance(dry, bool): raise ValueError("dry_run")
    if not isinstance(metadata, dict): raise ValueError("metadata")
    return {"name": name.strip(), "targets": output_targets, "timeout_seconds": timeout, "retries": retries, "dry_run": dry, "metadata": clean(metadata)}
