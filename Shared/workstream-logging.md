# Legacy Workstream Logging - Reference Only

*Superseded by proportional, evidence-focused state in the stable Core. Do not log private reasoning or every low-value action. Retained for migration and evaluation.*

## Where
Each repo has a `workstreams/` directory at its root (create it if missing):

```
workstreams/
  INDEX.md                 # the running index of all workstreams + status
  2026-07-12-<slug>.md     # one file per unit of work (a feature, fix, or investigation)
```

## The index (`workstreams/INDEX.md`)
A table, newest first:

| Date | Workstream | Status | Summary |
|---|---|---|---|
| 2026-07-12 | auth-refactor | 🟡 in-progress | Extracting auth into middleware |

Status legend: 🟢 done · 🟡 in-progress · 🔴 blocked · ⚪ planned.

## The workstream doc
Each `YYYY-MM-DD-<slug>.md` contains:

- **Goal** — what and why (link the request/issue).
- **Plan** — the steps, checked off as you go.
- **Decisions** — choices made and the reasoning (so future agents don't relitigate them).
- **Changes** — files touched and what changed.
- **Verification** — how you proved it works (commands, outputs, what you exercised).
- **Status** — done / next / blocked, with the concrete next action.
- **Open questions** — anything unresolved.

## Rules
- Update the workstream doc **as you work**, not only at the end. It is your externalized memory.
- Update `INDEX.md` whenever a status changes.
- Keep docs (README, module docs) in sync as part of the same change.
- On resuming, read `INDEX.md` first to reload context.

## Operating principles

- **Keep an append-only work journal at a stable path.** Read it first at the start of every session and update it last before ending. Each entry records what changed, what was attempted and failed and why, the current status, and the single next action. Keep a short index or table of contents at the top so a cold start reconstructs state in one read, and pair the journal read with a scan of recent version-control history. Append rather than rewrite — the trail of failed approaches is what stops the next session from re-walking dead ends.

- **Track scope in a machine-checkable ledger.** Hold the work as a structured, diffable list where each item carries testable completion criteria and a boolean status. Prefer a structured format (e.g. JSON) that is edited deliberately rather than free prose that invites optimistic self-grading. Flip an item to complete only after its verification actually passes.

- **Mark done and next unambiguously.** Designate exactly one "next" item so any resumed session has a single, obvious entry point. Move finished items into a done section instead of deleting them, preserving an auditable record of who changed what and when in the diff history.

- **Index durable learnings separately from the work log.** Maintain a skinny, always-loaded index that points to detail files loaded on demand — the same index-plus-detail discipline that keeps the journal cheap to read. Curate it: rename or prune stale notes so the memory does not drift from reality.

- **Keep every run resumable.** Assume the context can reset at any moment, so persist state to files rather than trusting in-session memory — anything not written down is lost on interruption or summarization. Commit or checkpoint at meaningful units with descriptive messages, using version control as both the recovery mechanism and the rollback path. For work spanning sessions, write a self-contained handoff that states what was accomplished, what remains, open questions, and the exact commands to resume. Keep the record both human-readable (for review and audit) and machine-readable (for the next run to parse).
