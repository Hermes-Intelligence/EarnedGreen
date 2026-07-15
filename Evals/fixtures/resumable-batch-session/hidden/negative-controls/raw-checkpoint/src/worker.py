import copy
import hashlib
import json

from .checkpoint import load_checkpoint, save_checkpoint


def run_batch(items, checkpoint_path, process, max_items=None):
    if max_items is not None and (isinstance(max_items, bool) or not isinstance(max_items, int) or max_items < 0):
        raise ValueError("max_items")
    batch = list(items)
    digest = hashlib.sha256(json.dumps(batch, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    state = load_checkpoint(checkpoint_path) or {"version": 1, "input_digest": digest, "completed_indices": [], "raw_items": batch}
    if state.get("input_digest") != digest:
        raise ValueError("mismatch")
    completed = set(state.get("completed_indices", []))
    processed = []
    budget = len(batch) if max_items is None else max_items
    for index, item in enumerate(batch):
        if index in completed or budget == 0:
            continue
        key = hashlib.sha256(f"{digest}:{index}".encode()).hexdigest()
        result = process(copy.deepcopy(item), key)
        completed.add(index)
        budget -= 1
        state["completed_indices"] = sorted(completed)
        state["last_result"] = result
        save_checkpoint(checkpoint_path, state)
        processed.append({"index": index, "result": result})
    return {"processed": processed, "completed": len(completed), "done": len(completed) == len(batch)}
