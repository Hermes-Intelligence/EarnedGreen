[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Run,
    [Parameter(Mandatory = $true)][ValidateSet('codex', 'claude')][string]$Provider,
    [string]$Model = 'provider-default',
    [ValidateSet('low', 'medium', 'high', 'xhigh')][string]$Effort = 'medium',
    [ValidateRange(1, 99)][int]$MaxTurns = 12,
    [ValidateRange(1, 120)][int]$MaxWallMinutes = 15,
    [ValidateRange(1, 20000)][int]$MaxFiles = 5000,
    [ValidateRange(1048576, 1073741824)][long]$MaxBytes = 52428800,
    [string]$DistroName = 'AgenticBench',
    [switch]$Execute,
    [string]$Root
)

$ErrorActionPreference = 'Stop'
if (-not $Root) { $Root = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) }
$rootPath = (Resolve-Path -LiteralPath $Root).Path
$runsRoot = (Resolve-Path -LiteralPath (Join-Path $rootPath 'Evals/runs')).Path
$runPath = if ([IO.Path]::IsPathRooted($Run)) { (Resolve-Path -LiteralPath $Run).Path } else { (Resolve-Path -LiteralPath (Join-Path $runsRoot $Run)).Path }
if (-not $runPath.StartsWith($runsRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Run escaped Evals/runs.' }
if ($Model -notmatch '^[A-Za-z0-9._:-]+$') { throw 'Model selector contains unsafe characters.' }
if ($Provider -eq 'claude' -and $Effort -eq 'xhigh') { throw 'Claude does not accept xhigh effort.' }

$manifest = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $runPath 'run-manifest.json') | ConvertFrom-Json
$workspace = (Resolve-Path -LiteralPath (Join-Path $runPath $manifest.workspace)).Path
if (-not $workspace.StartsWith($runPath + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Workspace escaped the run directory.' }
if (Get-ChildItem -LiteralPath $workspace -Force -Recurse | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint } | Select-Object -First 1) { throw 'Host workspace contains a reparse point.' }

$agentic = Join-Path $workspace '.agentic'
New-Item -ItemType Directory -Force -Path $agentic | Out-Null
Copy-Item -LiteralPath (Join-Path $runPath 'prompt.txt') -Destination (Join-Path $agentic 'BENCHMARK_PROMPT.txt') -Force

function Invoke-Wsl([string[]]$WslArguments) {
    $old = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $output = & wsl @WslArguments 2>&1 | Out-String
    $exitCode = $LASTEXITCODE
    $ErrorActionPreference = $old
    return [pscustomobject]@{ ExitCode = $exitCode; Output = $output.Trim() }
}

$versionPath = if ($Provider -eq 'codex') { '/home/agenticbench/.local/bin/codex' } else { '/home/agenticbench/.local/bin/claude' }
$version = Invoke-Wsl @('-d', $DistroName, '--', $versionPath, '--version')
$auth = if ($Provider -eq 'codex') {
    Invoke-Wsl @('-d', $DistroName, '--', $versionPath, 'login', 'status')
} else {
    Invoke-Wsl @('-d', $DistroName, '--', $versionPath, 'auth', 'status', '--json')
}
$authenticated = if ($Provider -eq 'codex') {
    $auth.ExitCode -eq 0
} else {
    if ($auth.ExitCode -ne 0) { $false } else { try { [bool](($auth.Output | ConvertFrom-Json).loggedIn) } catch { $false } }
}

$preview = [ordered]@{
    schema_version = 1
    provider = "$Provider-agenticbench"
    provider_version = $version.Output
    authenticated = $authenticated
    workspace = $workspace
    model = $Model
    effort = $Effort
    limits = [ordered]@{ max_turns = $MaxTurns; max_wall_minutes = $MaxWallMinutes; max_files = $MaxFiles; max_bytes = $MaxBytes }
    isolation = 'dedicated-wsl-no-windows-mount'
    execute = [bool]$Execute
}
if (-not $Execute) { $preview | ConvertTo-Json -Depth 8; exit 3 }
if ($version.ExitCode -ne 0) { throw "$Provider CLI is unavailable in $DistroName." }
if (-not $authenticated) { throw "$Provider login is required inside $DistroName." }

$providerLockPath = Join-Path $rootPath 'Evals/local/agenticbench-provider.lock'
try {
    $providerLock = [IO.File]::Open($providerLockPath, [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
} catch {
    throw 'Another AgenticBench provider adapter is active. Refusing concurrent workspace access.'
}
trap { if ($null -ne $providerLock) { $providerLock.Dispose() }; throw $_ }
$activeProvider = Invoke-Wsl @('-d', $DistroName, '-u', 'root', '--', 'bash', '-lc', "pgrep -x codex; pgrep -x claude; pgrep -f 'agenticbench-run-provider[.]sh'")
if ($activeProvider.Output) {
    $providerLock.Dispose()
    throw 'An orphaned provider process is active inside AgenticBench. Refusing workspace reset.'
}

$remoteWorkspace = '/srv/agenticbench/workspace'
$reset = Invoke-Wsl @('-d', $DistroName, '-u', 'root', '--', '/opt/agenticbench/bin/agenticbench-reset-workspace.sh')
if ($reset.ExitCode -ne 0) { throw 'Remote workspace reset failed.' }

$unc = "\\wsl.localhost\$DistroName\srv\agenticbench\workspace"
if (-not (Test-Path -LiteralPath $unc)) { $unc = "\\wsl$\$DistroName\srv\agenticbench\workspace" }
if (-not (Test-Path -LiteralPath $unc)) { throw 'AgenticBench workspace bridge is unavailable.' }
Get-ChildItem -LiteralPath $workspace -Force | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $unc -Recurse -Force }

$started = [datetimeoffset]::Now
$seconds = $MaxWallMinutes * 60
$providerResult = Invoke-Wsl @('-d', $DistroName, '-u', 'agenticbench', '--', '/opt/agenticbench/bin/agenticbench-run-provider.sh', $Provider, $Model, $Effort, [string]$MaxTurns, [string]$seconds)
$validation = Invoke-Wsl @('-d', $DistroName, '-u', 'root', '--', 'env', "AGENTIC_MAX_FILES=$MaxFiles", "AGENTIC_MAX_BYTES=$MaxBytes", '/opt/agenticbench/bin/agenticbench-validate-workspace.sh')

$copiedBack = $false
try {
    if ($validation.ExitCode -ne 0) { throw "Remote workspace validation failed: $($validation.Output)" }
    $returned = Join-Path $runPath 'artifacts/returned-workspace'
    if (-not $returned.StartsWith($runPath + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe returned workspace path.' }
    if (Test-Path -LiteralPath $returned) { Remove-Item -LiteralPath $returned -Recurse -Force }
    New-Item -ItemType Directory -Path $returned | Out-Null
    Get-ChildItem -LiteralPath $unc -Force | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $returned -Recurse -Force }
    if (Get-ChildItem -LiteralPath $returned -Force -Recurse | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint } | Select-Object -First 1) { throw 'Returned workspace contains a reparse point.' }
    & robocopy $returned $workspace /MIR /R:1 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -gt 7) { throw "Workspace synchronization failed with robocopy code $LASTEXITCODE." }
    $copiedBack = $true
}
finally {
    Invoke-Wsl @('-d', $DistroName, '-u', 'root', '--', '/opt/agenticbench/bin/agenticbench-reset-workspace.sh') | Out-Null
}

$actualModel = $null
$modelEvidence = 'not-reported'
$tokenUsage = $null
$reportedCostUsd = $null
$costBasis = 'not-reported-by-subscription-cli'
$eventsHostPath = Join-Path $workspace '.agentic/provider-events.jsonl'
if (Test-Path -LiteralPath $eventsHostPath) {
    $telemetry=& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $rootPath 'Evals/tools/read-provider-telemetry.ps1') -EventsPath $eventsHostPath -Provider $Provider|ConvertFrom-Json
    $actualModel=[string]$telemetry.actual_model
    if($actualModel){$modelEvidence='provider-event'}
    $tokenUsage=$telemetry.token_usage
    $reportedCostUsd=$telemetry.monetary_cost.amount_usd
    $costBasis=[string]$telemetry.monetary_cost.basis
}
if(-not $tokenUsage){$tokenUsage=[ordered]@{input_tokens=0;cached_input_tokens=0;cache_creation_input_tokens=0;cache_read_input_tokens=0;output_tokens=0;reasoning_output_tokens=0;total_observed_tokens=0;accounting='not-reported';source='not-reported'}}
if (-not $actualModel -and $Model -ne 'provider-default') { $actualModel = $Model; $modelEvidence = 'explicit-cli-selector' }
if (-not $actualModel) { $actualModel = 'unresolved-provider-default' }

$record = [ordered]@{
    schema_version = 1
    provider = "$Provider-agenticbench"
    provider_version = $version.Output
    authenticated = $authenticated
    model_requested = $Model
    actual_model = $actualModel
    model_evidence = $modelEvidence
    effort = $Effort
    started_at = $started.ToString('o')
    finished_at = [datetimeoffset]::Now.ToString('o')
    exit_code = $providerResult.ExitCode
    copied_back = $copiedBack
    workspace_validation = if ($validation.ExitCode -eq 0) { $validation.Output | ConvertFrom-Json } else { $null }
    events_path = '.agentic/provider-events.jsonl'
    token_usage = $tokenUsage
    monetary_cost = [ordered]@{ amount_usd = $reportedCostUsd; basis = $costBasis }
    isolation = 'dedicated-wsl-no-windows-mount'
    limits = $preview.limits
}
$record | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $runPath 'provider-execution.json')
$providerLock.Dispose()
$record | ConvertTo-Json -Depth 10
exit $providerResult.ExitCode
