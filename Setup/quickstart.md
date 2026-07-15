# Agentic Work - One-Page Quickstart

## Start anywhere

Fresh Claude and Codex sessions load the promoted manifest from `AgenticWorkBestPractices/Runtime/stable/manifest.json`. Global and repository pointers contain only a small bootstrap; long contracts and research candidates are not loaded automatically.

## Normal workflow

1. **Diagnose once:** `powershell -ExecutionPolicy Bypass -File tools/agentic.ps1 doctor -TargetRepo <repo>`
2. **Install safely:** `powershell -ExecutionPolicy Bypass -File tools/agentic.ps1 init -TargetRepo <repo>` — idempotent managed block; existing repo rules remain.
3. **Route the task:** `powershell -ExecutionPolicy Bypass -File tools/agentic.ps1 route -TargetRepo <repo> -Task "<task>"`
4. **Work from the Context Pack:** minimal Core plus selected task/risk modules.
5. **Prove completion:** run the objective checker and record relevant test/runtime evidence.

The route includes a capability profile. Resolve it with `agentic.ps1 model-recommend` only when useful. The result is scoped to the task/session, respects explicit user choice, and never silently changes the user's default model. Actual model and effort belong in evidence.

## Weekly research

Run `/weekly-research` in this repository. It reuses both the reviewed registry and the preserved Claude-v1 discovery inventory, rechecks due and pending-review sources, then performs bounded discovery across official docs, papers, benchmarks, YouTube, podcasts and practitioner/social watchlists.

Research writes only `Research/candidate-packages/<run-id>/` and a dated linked report. It never edits Stable, global pointers, sibling repos, Git history or remotes. Promotion happens separately after evals and human approval.

## Safety and status

- Stable guidance: `Runtime/stable/manifest.json` and `Core/runtime.md`.
- Candidate research has no authority.
- Explicit current user direction and repository policy follow `Core/policies/instruction-precedence.md`.
- Verdicts are PASS, FAIL, BLOCKED or NOT APPLICABLE; PASS requires evidence.
- No commit or push is performed by these setup/research commands.
