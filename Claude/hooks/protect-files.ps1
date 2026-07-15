# PreToolUse hook (Edit|Write): refuse edits to protected paths.
# The harness treats ONLY exit code 2 as a block. Emit the reason to stderr
# directly; a Write-Error under $ErrorActionPreference='Stop' would throw a
# terminating error and the process would exit 1, silently allowing the edit.
$ErrorActionPreference = "Stop"
function Deny([string]$reason) { [Console]::Error.WriteLine($reason); exit 2 }

try { $payload = [Console]::In.ReadToEnd() | ConvertFrom-Json }
catch { Deny "Hook payload is invalid; refusing an uninspectable file edit." }
$path = [string]$payload.tool_input.file_path
if ([string]::IsNullOrWhiteSpace($path)) { Deny "Hook payload has no file_path; refusing edit." }
$normalized = $path.Replace("\", "/")

# Secrets and immutable eval material, plus the Stable governance surface. Stable
# changes must go through a candidate package + tools/promote-candidate.ps1, not
# an in-place Edit/Write, so these are refused for the interactive edit tools.
$protected = @(
    "(^|/)\.env($|\.)",
    "(^|/)\.git/",
    "(^|/)secrets?/",
    "\.pem$",
    "\.key$",
    "(^|/)Evals/hidden/",
    "(^|/)Evals/fixtures/[^/]+/hidden/",
    "(^|/)Runtime/stable/",
    "(^|/)Runtime/releases/",
    "(^|/)Core/runtime\.md$",
    "(^|/)Core/policies/",
    "(^|/)Core/knowledge-modules/",
    "(^|/)Claude/BOOTSTRAP\.md$",
    "(^|/)Codex/BOOTSTRAP\.md$"
)
if ($protected | Where-Object { $normalized -match $_ }) {
    Deny "Protected path (secret or Stable governance surface; change Stable via a candidate package + promotion): $path"
}
exit 0
