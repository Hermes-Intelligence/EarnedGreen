import copy
import hashlib
import json

from .checkpoint import load_checkpoint, save_checkpoint


def _digest(items):
    try:
        encoded = json.dumps(items, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except Exception as exc:
        raise ValueError("items must be canonical JSON values") from exc
    return hashlib.sha256(encoded).hexdigest()


def run_batch(items, checkpoint_path, process, max_items=None):
    if max_items is not None and (isinstance(max_items, bool) or not isinstance(max_items, int) or max_items < 0):
        raise ValueError("invalid max_items")
    batch = list(items)
    digest = _digest(batch)
    state = load_checkpoint(checkpoint_path)
    if state is None:
        state = {"version": 1, "input_digest": digest, "completed_indices": []}
    elif state["input_digest"] != digest:
        raise ValueError("checkpoint input mismatch")
    completed = set(state["completed_indices"])
    processed = []
    remaining_budget = len(batch) if max_items is None else max_items
    for index, item in enumerate(batch):
        if index in completed or remaining_budget == 0:
            continue
        key = hashlib.sha256(f"{digest}:{index}".encode("utf-8")).hexdigest()
        result = process(copy.deepcopy(item), key)
        completed.add(index)
        remaining_budget -= 1
        state["completed_indices"] = sorted(completed)
        save_checkpoint(checkpoint_path, state)
        processed.append({"index": index, "result": result})
    return {"processed": processed, "completed": len(completed), "done": len(completed) == len(batch)}
