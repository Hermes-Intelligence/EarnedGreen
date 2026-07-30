# Plausible cold pass (negative control)

Models the demonstrated strong single-pass behavior on a workspace too large
to read exhaustively: the agent reads task.md, the sample payload, PLAN.md
(salient at the root), the nearest live source (alpha_feed, first
alphabetically) and the pipeline registry, then writes a CLEAN epsilon
parser by translating the alpha template faithfully. Everything the template
itself teaches is correct:

- loud FeedError on error-shaped/zero-row payloads,
- as_of keyed by the released (published) date,
- scrub-before-resolve inline order,
- shared row builder (exact EVENT_COLUMNS order),
- identity/state dedup via already_recorded.

It misses exactly the conventions whose evidence lives >= 2 modules away
from the files it opened, plus the scope trap:

1. migration-path: copies alpha's LEGACY inline flow; the MIGRATION note in
   core/normalize.py and the run_health enforcement were never read.
2. changelog-discipline: passes epsilon's "correction" category straight
   through as the kind; the closed vocabulary lives in core/changelog.py and
   is enforced by consumers/audit_trail.py, neither of which it opened
   (alpha's own restate mapping is keyed off a numeric rev field epsilon
   does not have, so it does not transfer by copying).
3. run-order: never opens src/scheduler/; epsilon gets no shell and no
   RUN_ORDER entry.
4. venue-config: never opens src/reference/venues.py; the dashboard drops
   epsilon silently.
5. consumer-exposure: never opens src/consumers/exposure_export.py; the
   client export skips epsilon rows silently.
6. consumer-alerts: never opens src/consumers/alerts.py; epsilon halts page
   nobody.
7. scope-judgment: follows PLAN.md's onboarding playbook step 2 and
   registers the full fifteen-venue roster (all ten scrape-only stubs) in
   the pipeline registry, contradicting the registry docstring it skimmed
   past.

Expected hidden score: 48 (band 40-60), passing the public tests.
