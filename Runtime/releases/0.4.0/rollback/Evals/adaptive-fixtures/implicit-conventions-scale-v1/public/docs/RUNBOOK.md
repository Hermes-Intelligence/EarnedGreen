# WIRE ops runbook

## The daily run

The scheduler driver executes `src/scheduler/registry.RUN_ORDER` strictly in
order: the sources block first, then resolution, exports, audit. Each source
shell pulls its venue's raw payload for the day and hands it to
`pipeline.ingest`; shells are thin on purpose and carry no logic beyond the
handoff.

If a venue has no drop for the day the shell is a no-op; the audit stage
still runs and the digest notes the venue's absence.

## When a source fails loudly

FeedError from a source aborts that venue's load only. Do NOT patch a source
to return an empty batch: downstream reads "no rows" as "no news", which is
exactly the silent gap the loud failure exists to prevent. Re-run the shell
after ops confirms the venue's feed is healthy.

## Store corruption / disaster recovery

Use `src/scheduler/backfill.py` with an ops incident ticket. Backfill is the
only sanctioned caller of the pipeline's `rebuild=True` switch; scheduled
ingestion never rebuilds. After a backfill, notify the desks: every
point-in-time answer previously given out must be re-derived.

## Re-runs

Re-running a source shell for the same day is safe: event-state hashing
(core/identity.py + changelog.already_recorded) dedups unchanged notices and
records changed ones as new rows.

## Adding a venue (summary)

Follow the conventions where they are enforced - the owning module's
docstring is the checklist. The short version: parser in `src/sources/`,
registration in `src/pipeline.py`, venue entry in `src/reference/venues.py`,
shell + `RUN_ORDER` placement in `src/scheduler/`, and the consumer
registries that key on source or venue. The audit stage will tell you what
you missed only for the change log; the client-facing views skip unknown
sources and venues silently by design.
