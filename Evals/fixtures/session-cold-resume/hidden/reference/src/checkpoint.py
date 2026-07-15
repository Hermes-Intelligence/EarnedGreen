import json, os, tempfile
from datetime import datetime, timezone
from pathlib import Path

REQUIRED = {"schema_version","objective_id","task","status","updated_at","decisions","evidence","blockers","next_action","changed_paths"}
SENSITIVE = ("secret", "token", "password", "credential")

def _clean(value):
    if isinstance(value, dict):
        return {k: _clean(v) for k,v in value.items() if not any(word in str(k).lower() for word in SENSITIVE)}
    if isinstance(value, list): return [_clean(x) for x in value]
    return value

def _validate(state):
    if not isinstance(state, dict) or not REQUIRED.issubset(state): raise ValueError("checkpoint structure")
    if not isinstance(state["next_action"], str) or not state["next_action"].strip(): raise ValueError("next_action")
    if not isinstance(state["updated_at"], str): raise ValueError("updated_at")
    try: datetime.fromisoformat(state["updated_at"].replace("Z", "+00:00"))
    except Exception as exc: raise ValueError("updated_at") from exc

def save_checkpoint(path, state):
    cleaned = _clean(state); _validate(cleaned)
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(cleaned, f, ensure_ascii=False, indent=2); f.flush(); os.fsync(f.fileno())
        os.replace(temp_name, path)
    except Exception:
        try: os.unlink(temp_name)
        except FileNotFoundError: pass
        raise

def load_checkpoint(path, max_age_hours=168, now=None):
    try:
        with open(path, encoding="utf-8") as f: state = json.load(f)
    except Exception as exc: raise ValueError("malformed checkpoint") from exc
    _validate(state)
    updated = datetime.fromisoformat(state["updated_at"].replace("Z", "+00:00"))
    if updated.tzinfo is None: raise ValueError("updated_at must be timezone-aware")
    current = now or datetime.now(timezone.utc)
    if state["status"] in {"in_progress","blocked","awaiting_review"} and (current - updated).total_seconds() > max_age_hours * 3600:
        raise ValueError("stale checkpoint")
    return state
