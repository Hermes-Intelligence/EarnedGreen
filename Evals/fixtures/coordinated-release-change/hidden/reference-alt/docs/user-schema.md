# User schema rollout

## Expand phase
During expand the legacy `email` field is retained so existing readers keep working, while writers start emitting `primary_email`.

## Migrate phase
Run the idempotent, cursor-based backfill in bounded batches and monitor legacy reads, conflicts and backfilled rows.

## Contract phase
Only after old-reader traffic and legacy-read metrics reach zero do we drop the legacy `email` field.

## Rollback phase
Rollback keeps both fields readable and restores old writers without deleting `primary_email` data.
