import json

def save_checkpoint(path, state):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f)

def load_checkpoint(path, max_age_hours=168, now=None):
    with open(path, encoding="utf-8") as f:
        return json.load(f)
