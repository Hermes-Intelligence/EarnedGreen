import copy
import hashlib
import json

from .checkpoint import save_checkpoint


def run_batch(items, checkpoint_path, process, max_items=None):
    if max_items is not None and (not isinstance(max_items, int) or max_items < 0):
        raise ValueError("max_items")
    batch = list(items)
    digest = hashlib.sha256(json.dumps(batch, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    limit = len(batch) if max_items is None else max_items
    processed = []
    for index, item in list(enumerate(batch))[:limit]:
        key = hashlib.sha256(f"{digest}:{index}".encode()).hexdigest()
        processed.append({"index": index, "result": process(copy.deepcopy(item), key)})
    save_checkpoint(checkpoint_path, {"version": 1, "input_digest": digest, "completed_indices": [item["index"] for item in processed]})
    return {"processed": processed, "completed": len(processed), "done": len(processed) == len(batch)}
