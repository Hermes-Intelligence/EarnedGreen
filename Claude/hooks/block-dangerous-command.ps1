# PreToolUse hook: flag destructive shell commands for human review.
# The harness treats ONLY exit code 2 as a block. Do NOT use Write-Error to emit
# the reason: with $ErrorActionPreference='Stop' a Write-Error throws a terminating
# error, the script unwinds, and the process exits 1 -- so the block is silently
# ignored and the command runs. Emit to stderr directly, then `exit 2`.
$ErrorActionPreference = "Stop"
function Deny([string]$reason) { [Console]::Error.WriteLine($reason); exit 2 }

try { $payload = [Console]::In.ReadToEnd() | ConvertFrom-Json }
catch { Deny "Hook payload is invalid; refusing an uninspectable command." }
$command = [string]$payload.tool_input.command
if ([string]::IsNullOrWhiteSpace($command)) { Deny "Hook payload has no command; refusing execution." }

# Each pattern is scoped with [^|;&]* so a lookahead cannot leak across a pipe or
# command separator. Flag order and abbreviation are handled so reversed/aliased
# variants (e.g. `-Force -Recurse`, `rm -fr`, `ri`) cannot slip past.
$patterns = @(
    # git force-push: --force, -f, --force-with-lease, or a `+refspec`
    "(?i)\bgit\s+push\b[^|;&]*(--force\b|--force-with-lease\b|\s-f\b)",
    "(?i)\bgit\s+push\b[^|;&]*\s\+[A-Za-z0-9._/-]+(:|\b)",
    "(?i)\bgit\s+reset\s+--hard\b",
    "(?i)\bgit\s+clean\b[^|;&]*-[A-Za-z]*f",
    # rm with recursive AND force in any flag arrangement (short combined, split, or long)
    "(?i)\brm\b(?=[^|;&]*(-{1,2}[A-Za-z]*r|--recursive))(?=[^|;&]*(-{1,2}[A-Za-z]*f|--force))",
    # PowerShell Remove-Item / aliases with -Recurse and -Force in any order or abbreviation
    "(?i)\b(Remove-Item|ri|rmdir|rd|del|erase)\b(?=[^|;&]*-Rec)(?=[^|;&]*-Fo)",
    # cmd recursive directory removal
    "(?i)\b(rd|rmdir)\b[^|;&]*\s/s\b",
    # disk / filesystem destruction
    "(?i)\bFormat-Volume\b|\bClear-Disk\b|\bmkfs\b"
)
foreach ($p in $patterns) {
    if ($command -match $p) { Deny "Potentially destructive command requires explicit human review: $command" }
}
exit 0
