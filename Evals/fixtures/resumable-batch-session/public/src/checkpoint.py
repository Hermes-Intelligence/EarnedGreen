import json
from pathlib import Path


def load_checkpoint(path):
    target = Path(path)
    if not target.exists():
        return None
    return json.loads(target.read_text(encoding="utf-8"))


def save_checkpoint(path, data):
    Path(path).write_text(json.dumps(data), encoding="utf-8")
