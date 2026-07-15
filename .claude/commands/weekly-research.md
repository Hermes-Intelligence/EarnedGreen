---
description: Run candidate-only weekly research without touching stable guidance or Git
---

Execute `Research/engine/research-brief.md` exactly.

First initialize a new candidate with `Research/engine/new-candidate.ps1`. Reuse its merged snapshot of the reviewed registry and Claude-v1 migration inventory; review pending sources and recheck due sources before bounded discovery. If the model catalog is due or a release is detected, generate only a candidate refresh plan from official provider sources. Verify every atomic claim, including platform deep dives, and reject claims without an explicit verifier verdict.

Write only inside the new `Research/candidate-packages/<run-id>/` and its dated Research Output. Produce a claim ledger, rejected claims, proposed source-registry patch, proposed changes, eval plan, Markdown report and PDF with clickable source hyperlinks.

Do not edit Stable, Core, platform bootstrap files, global pointers or sibling repositories. Do not commit or push. Finish at `awaiting-eval`; promotion is a separate human-approved workflow.
