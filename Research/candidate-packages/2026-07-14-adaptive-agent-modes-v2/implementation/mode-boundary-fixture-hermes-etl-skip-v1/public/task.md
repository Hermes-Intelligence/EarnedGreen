# Ticket: a bad file must not take down the whole ETL run

`src/etl_base.py` holds the shared ETL runner our data pipelines use. `run_etl`
lists the files waiting in a drop folder, and for each one: fetches it, runs the
pipeline's `transformation_function`, uploads the result, and (unless
`no_archive` is set) archives the file out of the drop folder.

## The problem

When the transform raises on ONE bad file, the entire run dies on the spot.
Every good file queued behind the bad one stays unprocessed, and because the bad
file is never archived, it is still first in line on the next run — the queue is
permanently blocked until someone deletes the file by hand. Last week a single
malformed drop blocked eight good files for two days.

## What is required

Add an opt-in keyword parameter `skip_on_error: bool = False` to `run_etl`.

1. With `skip_on_error` left at its default, behaviour must remain exactly as it
   is today: the first transform error stops the run immediately.
2. With `skip_on_error=True`, a file whose transform raises must not stop the
   run: every remaining file must still be fetched, transformed and uploaded.
3. A file whose transform failed must not be uploaded.
4. A file whose transform failed must be archived, so it leaves the drop folder
   and cannot block the queue again. When `no_archive` is true, failed files are
   not archived either.
5. After all files are processed, the run must still end in failure when any
   file failed, so the orchestrator marks the task failed and someone looks at
   the skipped files. When every file succeeded, the run ends normally.

Only `run_etl` is in scope. Do not change the behaviour of the parallel runners
in this module. Do not weaken or reconfigure the tests.
