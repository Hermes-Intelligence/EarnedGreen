# Risk discovery — failure modes that really happened

These are SEED EXAMPLES from a real product postmortem (22 defects in one
build). They exist to provoke thinking about THIS task's surfaces while you
fill the spec's `surface_inventory` and `risk_register`. They are a discovery
sample, not the universe: **novel failure classes are expected, and this list
must never be treated as a rubric or a coverage checklist.** Your risk register
is judged on traceability to the surfaces you enumerated from the code, not on
matching these categories.

- **silent-failure** — an external fetch/write whose failure looks like
  success. Real cases: an API returned an `{"error": ...}` payload at HTTP 200
  and zero rows loaded silently; reversed arguments to an upload call meant a
  snapshot was never saved, silently; missing error sentinels. Think: what does
  failure LOOK like on each I/O surface, and does the code fail loudly?
  Acceptance-test shapes: zero-rows guard, error sentinel, output-exists check.
- **verifier-validity** — a cross-check, confidence gate or QA instrument
  trusted without known-answer tests. Real cases: a broken regex cross-check
  was the confidence arbiter (mis-parsed "1,332" as 332, took max-id instead of
  count, false-flagged 48/57 records); a case-sensitive offline check missed
  "eKW" and nearly caused a "fix" of a non-bug. Validate the validator first.
- **distribution-coverage** — a parser/extractor designed from an
  unrepresentative sample. Real case: the original parser targeted the RAREST
  document format (~8% of the corpus). Measure the format distribution on a
  representative sample BEFORE choosing an approach.
- **domain-invariants** — cumulative/stock-vs-flow, dedup and restatement
  semantics discovered mid-flight destabilize everything built before them.
  Real cases: documents re-list prior items (needed new|prior tagging);
  cross-document deltas were non-monotonic; amendments double-counted ~3%.
  These belong in `convention_inventory` and `decision_points` up front.
- **fresh-deploy** — cold-start from zero as an acceptance test. Real case: a
  fresh deploy failed because NO entrypoint applied the schema.
- **ambiguity-defer** — when a value is genuinely ambiguous (e.g. dual ratings
  "2,500 ekW (2,250 standby)"), the pinned behavior is DEFER/flag for review,
  never guess; guessing produced tier-dependent, unstable results.
- **artifact-concurrency** — result artifacts need a single writer. Real case:
  a stray background process double-wrote a results file (353 vs 198 lines).

Use these to interrogate the surfaces you actually found in the workspace.
Then ask: what failure mode does THIS task enable that none of these describe?
That question is the point of the exercise.
