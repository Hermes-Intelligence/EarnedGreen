import json
import os
from pathlib import Path


def load_checkpoint(path):
    target = Path(path)
    if not target.exists():
        return None
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError("malformed checkpoint") from exc
    if not isinstance(value, dict) or set(value) != {"version", "input_digest", "completed_indices"} or value["version"] != 1 or not isinstance(value["input_digest"], str) or not isinstance(value["completed_indices"], list):
        raise ValueError("unsupported checkpoint")
    indices = value["completed_indices"]
    if any(isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in indices) or indices != sorted(set(indices)):
        raise ValueError("invalid indices")
    return value


def save_checkpoint(path, data):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, target)
