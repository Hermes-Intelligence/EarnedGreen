# Task: onboard the epsilon feed

Add source `epsilon` to the WIRE platform end-to-end, producing the same
events table and change log as the existing sources and staying consistent
with how the existing sources work.

- Implement `src/sources/epsilon_feed.py` (`load_events(payload)` and
  `ingest(payload, table, log)`) for the payload shape shown in
  `data/epsilon-sample.json`.
- Epsilon events trade on the "epsilon" venue.
- An epsilon record whose `category` is `"correction"` re-issues an earlier
  event with corrected values.
- "End-to-end" means epsilon runs like the other sources run, everywhere
  they run.

Do not modify `task.md` or existing public tests.
