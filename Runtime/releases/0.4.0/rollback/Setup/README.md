# Setup — Human Cheatsheets

Practical, human-facing guides (Markdown + PDF): how to start an agent so it obeys the best practices, the key shortcuts/commands, and the everyday workflows for Claude Code and Codex.

Regenerated whenever the research run changes the contracts, or on demand. *(Populated after research pass v1.)*

Benchmark documentation is maintained in `Setup/benchmarking/benchmarking-handbook.md` with a matching visually verified PDF and one-page quick reference.

## Clone-to-ready

From a fresh clone on Windows:

```powershell
powershell -ExecutionPolicy Bypass -File setup.ps1 -InstallCodex -GlobalPointers
powershell -ExecutionPolicy Bypass -File setup.ps1 -LoginCodex
powershell -ExecutionPolicy Bypass -File setup.ps1
```

The first command installs the current official Codex npm release and a compatible Node LTS only inside the WSL user's `~/.local`, refreshes pointers, proves mount-namespace isolation and runs self-tests. Authentication is deliberately a separate interactive step. Re-running setup is idempotent and writes machine-local provider/isolation status only under ignored `Evals/local/`.

## Subscription benchmark environment

Use a separate, empty WSL distribution for unattended benchmark runs:

```powershell
powershell -ExecutionPolicy Bypass -File Setup/benchmark.ps1 -Create -LoginCodex -LoginClaude -RefreshProviderCatalog
```

The login is a one-time human OAuth step. Normal restarts require neither setup nor login. Before a benchmark, `doctor-agenticbench.ps1` verifies the dedicated user, private home, missing `sudo`, disabled Windows interop, unmounted `C:`, root-owned runner, both CLIs and both authentication booleans. No credentials, account identifiers or raw authentication output are written to the repository.
