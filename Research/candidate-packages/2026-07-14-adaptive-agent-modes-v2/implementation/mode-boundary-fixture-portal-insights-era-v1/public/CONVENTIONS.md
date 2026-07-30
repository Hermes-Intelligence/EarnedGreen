# Payload conventions for the source-discovery insights layer

The standards every analytics response is held to. They apply wherever the
relevant payload is produced.

## Buckets

* Buckets are always presented in canonical size order:
  `core_10`, `extended_30`, `complete_50`, `beyond_80`; labels outside the
  canon come last. Never alphabetical, never storage order.
* The buckets payload carries, per bucket: its label, source count, coverage
  percentage, question coverage, geographic assessment and geographic flags,
  and the quality-gate fields.
* Page-level aggregates accompany the per-bucket rows:
  - `geographic_flags`: one flat list concatenating every bucket's
    list-valued flags;
  - `quality_gate_results`: only the dict-valued gate entries, collected in
    bucket order;
  - `builder_method`: the last non-null value across buckets, defaulting to
    `"heuristic"`;
  - `llm_calls_used`: the maximum across buckets' integer values.

## The question-source graph

* Each edge couples a question number with a source domain and carries the
  bucket label, strength and reasoning — AND is enriched with the matching
  source's viability score and source type (one source per (run, domain);
  a domain with no matching source yields nulls, never a dropped edge).

## Coverage report

* The report tolerates a result summary stored either as a JSON object or as
  a JSON-encoded string; unparseable content degrades to `{}`, never to an
  error.

## Serialization

* Every payload is JSON-safe end to end: timestamps as ISO strings, UUIDs as
  strings, SQL numerics as JSON numbers. A response must never fail to
  serialize because of a database type.

## Empty versus missing

* A run id that does not exist is a 404.
* A run that exists but has no pipeline run yet returns the endpoint's
  minimal empty shape (empty list or empty object) with a 200 — analytics
  never 404 on a merely-unstarted run.
* The countries endpoint is the historical exception: it returns
  `{"countries": []}` for both cases.

## What must never regress

* Portfolio analysis, tag taxonomy, strategic briefing, coverage matrix and
  countries answer exactly as they do today.
* The sources list keeps its response contract (`sources`, `total`, `page`,
  `pages`; 20 rows per page).
