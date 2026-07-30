# Research Candidate Governance

Research may write only inside a new `Research/candidate-packages/<run-id>/` directory and dated research-outputs. It must not modify Stable, Core, platform bootstrap, global pointers, sibling repositories, Git history or remote systems.

Every candidate contains:

- run manifest and tool/model versions,
- source registry snapshot and proposed source updates,
- claim ledger with one verifier verdict per claim,
- rejected and unresolved claims,
- proposed guidance changes as a diff or patch,
- eval and ablation plan,
- impact and rollback analysis,
- Markdown report and PDF with clickable source links.

Promotion is a separate, explicit, human-approved operation after required evals pass.
