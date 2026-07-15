# Claude Stable Bootstrap

1. Read `Core/runtime.md` (the manifest that routed you here already points to it; do not re-read the manifest).
2. Preserve explicit current user direction and repository-specific rules according to `Core/policies/instruction-precedence.md`.
3. Before substantive work, run `tools/preflight.ps1 -Mode core -TargetRepo <current-repo>`. Run it yourself; do not ask the user to repeat setup when the persistent checks pass. Read `workstreams/current.json` when continuing this source-of-truth repository.
4. For substantive work, create a task fingerprint with `tools/route.ps1` and load only the selected Context Pack modules.
5. Use `tools/preflight.ps1 -Mode benchmark` immediately before provider-backed benchmark runs. It adds live authentication and isolation checks. Run the full `setup.ps1` only when preflight reports `setup_required`; normal reboot or a new session does not require reinstall or login.
6. Run `tools/doctor.ps1` for deeper diagnostics when preflight fails or setup, discovery, hooks or platform compatibility is uncertain.
7. Use Claude-specific mechanisms only when the installed version confirms they exist. The long `Claude/OPERATING_CONTRACT.md` is reference material, not always-on law.
