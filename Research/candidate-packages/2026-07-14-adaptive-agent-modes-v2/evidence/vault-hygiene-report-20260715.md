# Vault Hygiene Report - 2026-07-15

Report-only scan; nothing was modified. Every repo-level finding is informational
and awaits human review. Package-level broken references gate the candidate suite.

## Headline

- Broken cross-references: **0** (candidate package: 0)
- Unmentioned tools: **0**
- Stale items: **0**
- Contradiction candidates (human review): **3**
- Orphans: **10**

## Contradiction candidates (human review required)

- [v1-workflow-assertion] `workstreams/2026-07-12-bootstrap-agentic-best-practices.md`: mentions research-workflow.js without a v1/legacy/deprecated marker while the v2 runbook exists
- [v1-workflow-assertion] `workstreams/2026-07-12-bootstrap-agentic-best-practices.md`: mentions engine/state.json without a v1/legacy/deprecated marker while the v2 runbook exists
- [package-status-divergence] `2026-07-14-adaptive-agent-modes-v2`: run-manifest.json status='boundary-campaign-invalid-fixture-repair-required' vs handoff.json status='research-utilization-layer-added-suite-23-of-23-green-awaiting-owner-review'

## Orphans

- [unlinked-finding] `F-2026-07-12-001`: in findings-index.json but justifies no rule in claims-rules-map.json
- [unlinked-finding] `F-2026-07-12-002`: in findings-index.json but justifies no rule in claims-rules-map.json
- [unlinked-finding] `F-2026-07-12-003`: in findings-index.json but justifies no rule in claims-rules-map.json
- [unlinked-finding] `F-2026-07-12-004`: in findings-index.json but justifies no rule in claims-rules-map.json
- [unlinked-finding] `F-2026-07-12-005`: in findings-index.json but justifies no rule in claims-rules-map.json
- [unlinked-finding] `F-2026-07-12-006`: in findings-index.json but justifies no rule in claims-rules-map.json
- [unlinked-finding] `F-2026-07-12-007`: in findings-index.json but justifies no rule in claims-rules-map.json
- [unlinked-finding] `F-2026-07-12-008`: in findings-index.json but justifies no rule in claims-rules-map.json
- [unlinked-finding] `F-2026-07-12-014`: in findings-index.json but justifies no rule in claims-rules-map.json
- [unlinked-finding] `F-2026-07-12-018`: in findings-index.json but justifies no rule in claims-rules-map.json

## Honest limits

- Contradiction detection is heuristic grep, labeled candidates only; semantic
  contradictions (a stale count or claim inside prose) are not detected.
- Markdown scanning covers the declared knowledge surfaces, not every file.
- Workstream staleness reads structured `updated_at` fields only; prose logs
  without dates are not aged.
