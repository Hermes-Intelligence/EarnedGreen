# Weekly Research - Candidate-Only Runbook

Research is untrusted until promoted. A run may write only to a new candidate package and its dated report output. It must not edit `Runtime/stable/`, `Core/`, `Claude/BOOTSTRAP.md`, `Codex/BOOTSTRAP.md`, global pointers, sibling repositories or Git history.

This is the authoritative (v2) runbook. The legacy `Research/engine/state.json`, `changelog.md` and `research-workflow.js` are v1 reference-only and are **not** part of this flow: a candidate-only run does **not** read them as state and must **not** write them. All per-run state (claims, verdicts, source patch, coverage, history) lives inside the run's own candidate package under `Research/candidate-packages/<run-id>/`.

## 1. Initialize

Run `powershell -ExecutionPolicy Bypass -File Research/engine/new-candidate.ps1`. Record the returned candidate directory. Capture tool, model, harness and platform versions in `run-manifest.json`.

## 2. Reuse the durable source registry

Read the candidate's immutable source snapshot, which merges the reviewed `Research/sources/registry.json` and the complete `Research/sources/claude-v1-migration.json`. Review `pending-review` entries and recheck due active entries before broad discovery. Search for new sources only after registered sources and their linked references have been reviewed.

Source priority:

1. official docs/changelogs/repositories,
2. primary papers, benchmarks, standards and original studies,
3. production engineering reports and postmortems,
4. YouTube/conference/podcast transcripts,
5. practitioner and social watchlists.

Tier 4–5 sources generate leads. Corroborate technical and security claims with tier 1–2 evidence.

Propose registry additions/updates in `source-registry.patch.json`. Do not edit the stable registry.

If the model catalog is due or a provider/model release is detected, run `tools/model-refresh-plan.ps1` and propose a refreshed `Models/providers.json` inside the candidate package. Verify availability and version gates from official provider sources. Never write volatile model IDs into stable capability profiles, and never update the live provider catalog from research.

## 3. Research and verify every claim

Create one claim-ledger entry per atomic claim. All topic research and platform deep dives use the same independent verification stage. A claim without an explicit verifier verdict is rejected from candidate guidance.

Block synthesis when:

- a selected topic returns no result,
- a version-sensitive claim lacks a current primary source,
- citations do not directly support the statement,
- applicability/version is missing,
- claim IDs are duplicated,
- coverage of the run objective is incomplete.

Keep unsupported, refuted and expired claims in `rejected-claims.json` with reasons.

## 4. Produce a candidate, not a stable edit

Write:

- `claims.json`,
- `rejected-claims.json`,
- `source-registry.patch.json`,
- `proposed-changes.md` as a reviewable diff plan,
- `eval-plan.json`,
- a model-catalog candidate patch when due,
- `report.md` and `report.pdf`.

Do not apply the proposed changes.

## 5. Report with clickable sources

The report includes: scope, method, claim coverage, source changes, accepted/rejected claims, proposed repo changes, eval/ablation plan, expected impact, risks, rollback and a complete `## Sources` appendix. Every source is a Markdown hyperlink with its title, tier and access date. Render to PDF and verify URI annotations plus visual layout.

## 6. Promotion is separate

End the run with candidate status `awaiting-eval`. Promotion requires explicit human approval, required evals, objective coverage, source validation, a reviewed diff and a rollback manifest. Research never commits or pushes.
