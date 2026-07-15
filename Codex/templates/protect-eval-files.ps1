# The harness treats ONLY exit code 2 as a block. Emit to stderr directly; a
# Write-Error under $ErrorActionPreference='Stop' throws a terminating error and
# the process exits 1, silently allowing the patch.
$ErrorActionPreference = "Stop"
function Deny([string]$reason) { [Console]::Error.WriteLine($reason); exit 2 }

try { $payload = [Console]::In.ReadToEnd() | ConvertFrom-Json }
catch { Deny "Hook payload is invalid; refusing an uninspectable patch." }
$blob = ($payload | ConvertTo-Json -Depth 20 -Compress).Replace("\", "/")
$protected = @(
    "Evals/hidden/",
    "Evals/fixtures/[^/]+/hidden/",
    "\.agent-evals/hidden/",
    "immutable-eval/"
)
foreach ($pattern in $protected) {
    if ($blob -match $pattern) {
        Deny "Patch touches immutable evaluation material: $pattern"
    }
}
exit 0
