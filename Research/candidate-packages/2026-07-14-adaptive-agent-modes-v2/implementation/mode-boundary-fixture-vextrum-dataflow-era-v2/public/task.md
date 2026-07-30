# Task: the pipeline core is not up to production

The `pipeline/` package materializes intelligence events into workspace
records and runs per-record processing DAGs (`materializer.py`, `planner.py`,
`executor.py` over the `db.py` seam). It limps: operations keeps a list of
incidents against it, and the list is growing.

* **Materialization crashes in production.** Since selection criteria gained
  filters, `materialize_workspace` dies with a parameter error on every
  workspace that has any active criteria. Nothing materializes at all.
* **When it did run, it re-read everything, every time.** Each run swept the
  entire UDS events table from the beginning of time and re-attempted every
  record. UDS reads are metered; the quota burn was flagged twice. A run over
  a workspace that is already up to date should touch next to nothing and
  say that it did nothing.
* **Infrastructure split the databases.** UDS (the shared events store) now
  lives on its own server, reachable via the `UDS_DATABASE_URL` connection
  string; workspace tables stay on `DATABASE_URL`. The pipeline still opens
  only the one workspace connection and expects UDS tables inside it.
* **Re-running a batch redoes finished work.** When a run fails partway
  (one flaky component, one poisoned record), operators re-run the workspace —
  and every component of every record executes again from scratch, including
  steps that already succeeded under the current configuration. Completed
  work should be reused, not repeated; a step's stored output is there for
  downstream components to consume.

Rework the pipeline core until it honours `CONVENTIONS.md` (in this
workspace) — that file states the operational standards this pipeline is held
to, and it is what your work will be judged against. The database schema
available on both servers is documented in `SCHEMA.md`. Keep the module layout
(`pipeline/materializer.py`, `pipeline/planner.py`, `pipeline/executor.py`,
`pipeline/db.py`) and the public entry points (`materialize_workspace`,
`plan_workspace`, `execute_run`) as they are; do not add dependencies; do not
weaken or reconfigure the tests. What already behaves, keeps behaving: a
workspace with no active criteria or no active configuration is a clean no-op
today and must stay one.
