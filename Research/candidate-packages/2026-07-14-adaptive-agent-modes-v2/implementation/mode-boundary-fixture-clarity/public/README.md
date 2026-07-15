# Market-events ingestion

A small library that ingests trading-halt/resume events from multiple exchange
feeds into a shared product table and change log. Each feed delivers its own
raw payload shape; the source modules under `src/sources/` normalize the
records and hand them to the shared helpers (`rows`, `changelog`, `guard`,
`resolve`, `dates`).

Sources currently wired: `alpha`, `beta`. `gamma` is being added.
