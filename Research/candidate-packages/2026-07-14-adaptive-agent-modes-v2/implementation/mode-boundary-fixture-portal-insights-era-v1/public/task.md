# Task: the source-discovery insights layer is embarrassing the product

`hermes_intelligence/routes/vextrum.py` serves the admin portal's source
discovery analytics — run sources, buckets, coverage, the question-source
bipartite graph. The UI team and two client demos have filed a pile of
incidents against it:

* **The bucket chart is wrong or dead.** On several runs the buckets endpoint
  500s outright and the whole summary pane renders blank. When it does answer,
  buckets come back in arbitrary order — the chart shows `extended_30` before
  `core_10`; buckets must always present in canonical size order
  (core → extended → complete → beyond, unknown labels last).
* **There is no buckets endpoint on half the surface.** The UI needs
  `/runs/{run_id}/buckets`, `/runs/{run_id}/question-source-matrix` and
  `/runs/{run_id}/coverage-report`; today the frontend fakes them client-side
  from raw sources, badly.
* **Geographic flags vanish.** Each bucket row carries its own list of
  geographic flags, but the page-level flag banner is empty — the per-bucket
  flags are never lifted into a flat top-level list.
* **Quality-gate info is missing or nonsense** where it appears at all: the
  builder method shows blank, the LLM-call counter shows a random bucket's
  number instead of the run's maximum, and non-dict junk rows leak into the
  gate results.
* **The bipartite graph renders every node identically.** Its edges carry
  question↔domain links but no viability score or source type, so the UI
  cannot size or colour anything.
* **The coverage report shows empty** for runs where the pipeline stored the
  result summary as a JSON *string* rather than an object.
* Assorted complaints on the sources list too: multi-select filters
  (country / tier / intelligence function) and sorting misbehave, and
  follow-up runs' "new sources only" toggle shows old sources. Fix what you
  can — but the analytics payloads above are the fire.

Rework the module until it honours `CONVENTIONS.md` (in this workspace) —
that file states the payload standards this layer is held to, and it is what
your work will be judged against. `DATA.md` documents the tables and columns
available. Keep the module layout and route paths as they are; the
`hermes_intelligence.{db,auth,access_control}` seams are infrastructure —
consume them as documented, do not modify them. Do not add dependencies; do
not weaken or reconfigure the tests. What already behaves, keeps behaving:
portfolio analysis, tag taxonomy, strategic briefing, coverage matrix and the
countries endpoint are correct today and must not regress.
