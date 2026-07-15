[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$ManifestPath,
    [Parameter(Mandatory=$true)][ValidateSet("start","progress","failure","complete","status")][string]$Action,
    [string]$Fingerprint,
    [double]$CostIncrement = 0,
    [string]$Evidence
)
$ErrorActionPreference = "Stop"
$manifest = Get-Content -Raw -Encoding UTF8 -LiteralPath $ManifestPath | ConvertFrom-Json
$base = Split-Path -Parent (Resolve-Path -LiteralPath $ManifestPath).Path
$statePath = if ([IO.Path]::IsPathRooted($manifest.state_path)) { $manifest.state_path } else { Join-Path $base $manifest.state_path }
$killPath = if ([IO.Path]::IsPathRooted($manifest.kill_file)) { $manifest.kill_file } else { Join-Path $base $manifest.kill_file }
$now = [datetimeoffset]::Now
if (Test-Path -LiteralPath $statePath) { $state = Get-Content -Raw -Encoding UTF8 -LiteralPath $statePath | ConvertFrom-Json }
else {
    $state = [pscustomobject][ordered]@{ schema_version=1; loop_id=$manifest.id; status="ready"; started_at=$null; updated_at=$now.ToString('o'); iterations=0; failures=0; no_progress=0; cost=0.0; last_fingerprint=$null; stop_reason=$null; evidence=@() }
}
if ($state.loop_id -ne $manifest.id) { throw "Loop state does not match manifest." }
if ($Action -eq "start" -and $state.status -eq "ready") { $state.status="running"; $state.started_at=$now.ToString('o') }
elseif ($Action -eq "progress" -or $Action -eq "failure") {
    if ($state.status -ne "running") { throw "Loop is not running." }
    if (-not $Fingerprint) { throw "-Fingerprint is required for progress/failure." }
    $state.iterations = [int]$state.iterations + 1
    $state.cost = [double]$state.cost + $CostIncrement
    if ($Fingerprint -eq $state.last_fingerprint) { $state.no_progress = [int]$state.no_progress + 1 } else { $state.no_progress=0; $state.last_fingerprint=$Fingerprint }
    if ($Action -eq "failure") { $state.failures = [int]$state.failures + 1 }
    if ($Evidence) { $state.evidence = @($state.evidence) + $Evidence }
} elseif ($Action -eq "complete") {
    if (-not $Evidence) { throw "Completion requires -Evidence." }
    $state.status="complete"; $state.evidence=@($state.evidence)+$Evidence
}

$elapsed = if ($state.started_at) { ($now - [datetimeoffset]$state.started_at).TotalSeconds } else { 0 }
$stop = $null
if (Test-Path -LiteralPath $killPath) { $stop="kill-switch" }
elseif ([int]$state.iterations -ge [int]$manifest.budgets.max_iterations) { $stop="iteration-budget" }
elseif ([int]$state.failures -gt [int]$manifest.budgets.max_failures) { $stop="failure-ceiling" }
elseif ([int]$state.no_progress -ge [int]$manifest.budgets.max_no_progress) { $stop="no-progress" }
elseif ($elapsed -ge [double]$manifest.budgets.max_seconds) { $stop="time-budget" }
elseif ([double]$manifest.budgets.max_cost -gt 0 -and [double]$state.cost -ge [double]$manifest.budgets.max_cost) { $stop="cost-budget" }
if ($stop -and $state.status -ne "complete") { $state.status="stopped"; $state.stop_reason=$stop }
$state.updated_at=$now.ToString('o')
$parent=Split-Path -Parent $statePath; if(-not(Test-Path $parent)){New-Item -ItemType Directory -Force -Path $parent|Out-Null}
$state | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 -LiteralPath $statePath
$state | ConvertTo-Json -Depth 8
if ($state.status -eq "stopped") { exit 4 }
