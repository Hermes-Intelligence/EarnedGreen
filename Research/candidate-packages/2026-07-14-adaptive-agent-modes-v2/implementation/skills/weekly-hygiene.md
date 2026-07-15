---
description: Run the report-only vault hygiene scan and hand the findings to the owner without modifying anything
---

CANDIDATE ARTIFACT - this file is authored inside the candidate package. It becomes a
real command only when promoted to `.claude/commands/weekly-hygiene.md` through
`tools/promote-candidate.ps1` after explicit human approval.

Run the zero-provider vault hygiene scan:

```
python <promoted-path>/vault_hygiene.py --output-dir "Research Output/hygiene/<date>"
```

(Until promotion, the tool lives at
`Research/candidate-packages/2026-07-14-adaptive-agent-modes-v2/implementation/vault_hygiene.py`;
the intended promoted wrapper is `tools/vault-hygiene.ps1`.)

The scan covers the repo's knowledge surfaces - `Core/`, the Router catalog,
`Research/knowledge-base/`, `Research/sources/registry.json`, `workstreams/`, `Models/`
and candidate package docs - and reports four classes of drift:

1. **Cross-reference integrity** - files referenced by manifests, catalogs or markdown
   links that do not exist; tools that exist but no scanned doc mentions.
2. **Staleness** - model catalog `expires_at`, source registry `next_check`, active
   workstreams not updated within 7 days, claims past expiry/recheck.
3. **Contradiction candidates** - cheap targeted heuristics only (conflicting status
   for the same requirement id across ledgers, docs asserting v1 research-workflow
   artifacts where the v2 runbook exists, diverging candidate-package statuses).
   These are CANDIDATES for human review, never verdicts.
4. **Orphans** - knowledge modules in no catalog, findings never linked in the
   claims-rules map, workstream files missing from INDEX.md.

Then run the claims-rules validator so claim expiry flags dependent rules:

```
python <promoted-path>/claims_ledger.py --map <promoted-path>/claims-rules-map.json
```

Hard rules for this command:

- **NEVER delete, edit or "fix" anything the scan flags.** The output is a dated JSON +
  Markdown report; remediation is a separate, human-reviewed change (optionally a new
  candidate package proposing the fixes). Review-before-commit always.
- Do not commit or push. Do not touch Stable (`Core/`, `Router/`, `tools/`,
  `Runtime/stable/`), global pointers or sibling repositories.
- Summarize the headline numbers (broken refs / stale / contradiction candidates /
  orphans) to the owner and list the specific items needing a decision.
- If the scan itself errors, report the failure honestly; do not fabricate a clean pass.
