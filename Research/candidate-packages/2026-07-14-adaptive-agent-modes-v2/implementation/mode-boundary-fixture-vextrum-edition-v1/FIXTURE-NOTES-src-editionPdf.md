# Why `public/src/editionPdf.js` is not committed

It is a real VextrumFrontend subtree. `fixture_admission` materializes it into the
workspace at grade time from a LOCAL VextrumFrontend git ref (`local_source` in
fixture-contract.json): the before-state for the agent's workspace and the
negative control, the shipped rework for the reference.

Two reasons, both load-bearing:
  * proprietary isolation — no Vextrum code is committed into this repo;
  * the committed file would BE the answer.

THIS NOTE LIVES OUTSIDE public/ ON PURPOSE. It used to sit at public/src/README.md,
which `prepare_adaptive_run` copies straight into the agent's workspace — telling
the agent under test that it is inside a benchmark replaying git history against a
known "shipped rework". That is meta-leakage: an arm that knows it is being graded
against a real later commit is not the arm we meant to measure. Anything that
explains the fixture machinery belongs here, never in public/.

If you see editionPdf.js under public/src/ in a working tree, it is a scratch
artifact from a local run. Delete it; do not commit it.
