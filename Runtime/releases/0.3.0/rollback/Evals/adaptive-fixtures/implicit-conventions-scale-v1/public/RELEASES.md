# WIRE platform release notes

## v2.4 - 2026-06-30
- delta migrated to the shared house flow (core/normalize.house_flow);
  run_health now cross-checks delta's flow counter.
- exposure export: unresolved tickers annotated with their venue bucket.
- epsilon capture approved by the EU desk; parser scheduled next sprint.

## v2.3 - 2026-06-12
- gamma migrated to the shared house flow; first migration off the legacy
  inline pattern (alpha and beta remain grandfathered, see
  consumers/run_health._LEGACY_SOURCES).
- venue dashboard: holiday-session annotation from reference/calendars.

## v2.2 - 2026-05-28
- audit stage added to RUN_ORDER (audit_trail replay + run_health flags).
- kappa raw capture landed (parser pending; CSV with US month-first dates).

## v2.1 - 2026-05-10
- resolution ladder: containment rung gated by reference/ambiguity
  (AMBIGUOUS_BARE + length floor) after the PRIME misattribution incident.
- theta, mu raw captures landed (parsers pending).

## v2.0 - 2026-04-20
- change log made append-only end to end; restatements are new rows with
  kind="restate"; audit replay enforces the closed kind vocabulary.
- events table re-keyed by knowledge date (as_of = published_at) after the
  look-ahead audit; effective-date keying removed everywhere.

## v1.x (historical)
- v1 carried per-source ad-hoc row shapes and a mutable current-state
  table; both retired in v2.0. Do not resurrect v1 patterns from old
  captures.
