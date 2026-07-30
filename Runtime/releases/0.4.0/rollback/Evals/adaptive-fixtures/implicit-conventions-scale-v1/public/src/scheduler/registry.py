"""Production run order for the daily WIRE run.

Convention: every ingesting source has a thin shell module scheduled in the
sources block, BEFORE run_resolution. The blocks run strictly in RUN_ORDER:

    sources block  -> run_resolution -> run_exports -> run_audit

Adding a source to the pipeline registry without scheduling its shell here
means the source never runs in production, even though every unit test
passes - the pipeline knows the source, the scheduler never calls it.
Scrape-only stubs have no shell (there is nothing to run).

Position within the sources block is not significant; position ACROSS blocks
is (see run_resolution.py for why a late source silently vanishes from
exposure).
"""

RUN_ORDER = (
    "src.scheduler.run_alpha",
    "src.scheduler.run_beta",
    "src.scheduler.run_gamma",
    "src.scheduler.run_delta",
    "src.scheduler.run_resolution",
    "src.scheduler.run_exports",
    "src.scheduler.run_audit",
)
