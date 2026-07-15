# Task: make batch work safely resumable across cold sessions

Implement `run_batch(items, checkpoint_path, process, max_items=None)` in `src/worker.py`.

`process(item, idempotency_key)` performs the outward-facing unit of work and returns an arbitrary result. A session may stop after any successful item and a later process must resume without repeating completed work.

Exact contract:

- Materialize the input sequence once and compute a deterministic SHA-256 digest of its canonical JSON representation.
- The idempotency key for index `i` is the SHA-256 of `"{input_digest}:{i}"`.
- Persist exactly `{"version": 1, "input_digest": string, "completed_indices": [sorted unique integers]}`.
- Never store raw items, results, credentials or exception text in the checkpoint.
- Write checkpoints atomically through a sibling temporary file and `os.replace` after every successful item.
- A missing checkpoint starts new work. Malformed/unsupported checkpoints raise `ValueError` before processing.
- Reusing a checkpoint with different input raises `ValueError` before processing.
- `max_items` limits successful calls in this invocation; `None` means all remaining and negative/non-integer values raise `ValueError`.
- Pass a deep copy of each item to `process`; caller-owned input must not be mutated.
- If processing raises, propagate the exception while preserving evidence for earlier successful items.
- Return exactly `{"processed": [{"index": i, "result": result}, ...], "completed": integer, "done": boolean}`. `processed` contains only this invocation.

Do not modify `task.md` or existing public tests.
