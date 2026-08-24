# Workstream Logging

Apply when developing a feature, process or product — any work substantial enough to span more than a single trivial edit, to touch more than one repository, or to be resumed later or by another agent.

Maintain a durable **workstream**: a per-feature record kept current AS THE WORK HAPPENS, not reconstructed at the end. Each feature / process / product gets its own workstream, holding:

- a log of what is done, what is in progress, what is left; decisions made and why; open questions;
- the exact files, tables, functions and contracts touched, per repository — a single feature usually spans several, and is recorded in ONE workstream, never fragmented per repo;
- its artifacts (scripts, generated data, reports, design references) kept WITH the log, not scattered elsewhere.

Update the workstream before ending a work session and whenever a meaningful step lands, so context is never lost across sessions or between agents.

This policy governs THAT the workstream exists and stays current. WHERE it lives and its exact on-disk structure are specified by the repository — a repository or path rule specializes this Core policy (per instruction precedence). Design references (mocks, specs) are a separate concern: they belong with the tool or component that consumes them, not in the workstream log, which is a journal.

Completion of substantive work is blocked until its workstream reflects the final state: what shipped, what remains, and a concrete resumable next action.
