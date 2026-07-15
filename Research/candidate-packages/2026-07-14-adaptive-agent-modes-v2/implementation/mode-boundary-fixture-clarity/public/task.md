# Task: add the gamma feed

Add a new source `gamma` to the pipeline producing the same product table and
change log as the existing sources; keep everything consistent with how the
existing sources work.

- Implement `src/sources/gamma_feed.py` (`load_events(payload)` and
  `ingest(payload, table, log)`) for the gamma payload shape shown in
  `data/gamma-sample.json`.
- Gamma events trade on the "gamma" venue.
- A gamma record whose `type` is `"amend"` re-issues an earlier event with
  corrected values.

Do not modify `task.md` or existing public tests.
