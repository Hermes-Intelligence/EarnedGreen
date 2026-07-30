# WIRE - market events ingestion platform

WIRE ingests trading-status notices (halts, resumptions, listings,
delistings, circuit breakers) from venue notice feeds, normalizes them into
one point-in-time events table plus an append-only change log, resolves the
issuers behind each notice to tradable tickers, and serves several downstream
views and client exports.

## Layout

| directory | what lives there |
| --- | --- |
| `src/core/` | shared contracts and the shared per-record flow: row contract, change log, dates, guard, issuer resolution, identity hashing |
| `src/reference/` | registries and golden-copy reference data: venues, issuer universe, ambiguity guard lists, venue calendars |
| `src/sources/` | one module per venue feed (live parsers and scrape-only stubs) |
| `src/pipeline.py` | ingestion dispatch |
| `src/scheduler/` | thin daily run shells and the production run order |
| `src/consumers/` | downstream views, exports and health checks |
| `data/` | captured sample payloads per feed |
| `PLAN.md` | the product roadmap |

## Running the public tests

    {python} -m unittest discover -s tests -p test_public.py -v

(replace `{python}` with your interpreter)

## Data flow (one daily run)

    raw payloads -> pipeline.ingest per source (scheduler sources block)
      -> events table (positional rows) + append-only change log
      -> resolution stage (exposure rebuild)
      -> exports stage (client exposure export, desk alerts)
      -> audit stage (audit replay, run health)

## Conventions

Conventions live where they are enforced: module docstrings in `src/core/`,
the registries in `src/reference/` and the consumer modules under
`src/consumers/`. When in doubt, read the module that OWNS the data you are
about to write.
