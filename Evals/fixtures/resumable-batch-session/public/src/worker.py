import hashlib
import json

from .checkpoint import save_checkpoint


def run_batch(items, checkpoint_path, process, max_items=None):
    batch = list(items)
    digest = hashlib.sha256(json.dumps(batch, sort_keys=True).encode()).hexdigest()
    processed = []
    for index, item in enumerate(batch):
        key = hashlib.sha256(f"{digest}:{index}".encode()).hexdigest()
        processed.append({"index": index, "result": process(item, key)})
    save_checkpoint(checkpoint_path, {"version": 1, "items": batch, "completed_indices": list(range(len(batch)))})
    return {"processed": processed, "completed": len(batch), "done": True}
