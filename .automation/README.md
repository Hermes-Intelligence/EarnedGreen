# .automation

Scripts that power the self-improving loop.

## `md_to_pdf.py` — dated-PDF renderer
Zero-dependency Markdown → styled PDF via headless Chrome/Edge (no pip installs, so the unattended run never breaks on a missing package).

```bash
python .automation/md_to_pdf.py \
  --in "research-outputs/2026-07-12/report.md" \
  --out "research-outputs/2026-07-12/report.pdf" \
  --title "Agentic Best Practices — Research Report" \
  --subtitle "Weekly deep-research pass" \
  --date 2026-07-12
```
- If `--title` is omitted, the first `# H1` (or filename) is used and that H1 is stripped from the body so the cover page doesn't duplicate it.
- Set `CHROME_PATH` to override browser discovery. `--keep-html` leaves the intermediate HTML beside the PDF for inspection.
- Supported Markdown: headings, paragraphs, **bold**/*italic*/`code`/~~strike~~, links, images, blockquotes, fenced code, horizontal rules, ordered/unordered (nested) lists, and GFM pipe tables with alignment.

## The weekly research engine
The authoritative runbook is [`../Research/engine/research-brief.md`](../Research/engine/research-brief.md) — the candidate-only v2 flow. The legacy harness [`../Research/engine/research-workflow.js`](../Research/engine/research-workflow.js) and the `Research/engine/state.json`/`changelog.md` loop are v1 **reference-only** and are not executed by the current flow.

**To run it** (you-triggered): open Claude Code in the repo root and run `/weekly-research`. A run writes **only** to a new candidate package under `Research/candidate-packages/<run-id>/` (claims, rejected claims, `source-registry.patch.json`, a `proposed-changes.md` diff plan, `eval-plan.json`) plus a dated PDF report in `research-outputs/`. It performs **no** integration into the contracts/doctrine/knowledge-base, **no** edits to `Runtime/stable/`, `Core/`, the platform bootstraps or global pointers, and **no** commit or push. The run ends at candidate status `awaiting-eval` (awaiting approval).

**Promotion is a separate, human-approved step.** Applying a reviewed candidate to Stable runs via `tools/promote-candidate.ps1` only after required evals, objective coverage, source validation, a reviewed diff and a rollback manifest.

**Scoping a run** (incremental weeks): a run may target only the weak/stale topics; scope is passed as candidate args to the research brief. Running research requires explicit user opt-in (multi-agent orchestration).
