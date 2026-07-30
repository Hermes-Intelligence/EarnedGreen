# Operational conventions for the pipeline core

The standards the pipeline is held to. These rules apply wherever the relevant
behaviour lives in the package.

## Materialization

* Materialization is incremental per workspace: events that were already
  materialized in an earlier run must not be re-fetched wholesale from UDS on
  later runs. The pipeline tracks how far each workspace has been materialized
  and resumes from there.
* A materialization run reports how many records it actually added; an
  up-to-date workspace reports (near) zero, it does not silently re-count old
  events as new work.
* A record that already exists for a workspace is never duplicated
  (the insert is conflict-safe on the workspace/event pair).

## Databases

* UDS tables (`uds.*`) live on the UDS server: every read of them goes through
  a connection opened from `UDS_DATABASE_URL`. Workspace tables
  (`vextrum_v0.*`) stay on the connection from `DATABASE_URL`. No statement
  crosses servers.

## SQL

* Statements use the psycopg2 `%s` parameter style, and every placeholder is
  matched by exactly one parameter, in order. Dynamically assembled conditions
  must keep the placeholder list and the parameter list aligned.

## Execution

* A component step that already SUCCEEDED (or was SKIPPED) for a record under
  the current workspace configuration does not run again on a later run: its
  stored output is loaded and handed to downstream components exactly as if it
  had just run, and the run's stats say how much work was reused.
* Reuse is configuration-aware: work done under a different workspace
  configuration hash is stale and is redone, never reused.
* A component failure fails that record (remaining components of the record do
  not run), is recorded with a result code, and marks the run FAILED; other
  records still process.
* A record rejected by an upstream filter is recorded as SKIPPED, and
  downstream components see that it was skipped.

## What must never regress

* A workspace with no active selection criteria materializes nothing and
  reports zero, without touching UDS.
* A workspace with no active configuration, or a configuration with no
  components, plans nothing.
* Execution runs record their lifecycle (planned, running, completed or
  failed) and their stats truthfully.
