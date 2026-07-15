# User schema rollout

## Expand

Readers accept `email` and `primary_email`; writers emit `primary_email`. Legacy email is retained during expand for old readers.

## Migrate

Run the idempotent, cursor-based backfill in bounded batches and monitor legacy reads, conflicts and backfilled rows.

## Contract

Remove legacy `email` only after old-reader traffic and legacy-read metrics reach zero.

## Rollback

Rollback keeps both fields readable and restores old writers without deleting `primary_email` data.
