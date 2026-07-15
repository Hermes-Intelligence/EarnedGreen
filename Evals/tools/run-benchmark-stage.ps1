[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Campaign,
    [Parameter(Mandatory = $true)][ValidateSet('calibration', 'complex-screen', 'battery-sentinel', 'battery-diversity', 'smoke', 'directional', 'confidence', 'pilot')][string]$Stage,
    [ValidateRange(1, 6)][int]$MaxRunsThisInvocation = 4,
    [string]$Root
)

$ErrorActionPreference = 'Stop'
if (-not $Root) { $Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot) }
$rootPath = (Resolve-Path -LiteralPath $Root).Path
$path = if ([IO.Path]::IsPathRooted($Campaign)) { (Resolve-Path -LiteralPath $Campaign).Path } else { (Resolve-Path -LiteralPath (Join-Path $rootPath "Evals/experiments/$Campaign")).Path }
$campaignPath = Join-Path $path 'campaign.json'
$lockPath = Join-Path $path 'campaign.runner.lock'
try {
    $campaignLock = [IO.File]::Open($lockPath, [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
} catch {
    throw 'Another campaign runner is active. Refusing concurrent execution.'
}
trap { if ($null -ne $campaignLock) { $campaignLock.Dispose() }; throw $_ }
$stopPath = Join-Path $rootPath 'Evals/local/STOP'
if (Test-Path -LiteralPath $stopPath) { throw "Kill switch is active: $stopPath" }

$data = Get-Content -Raw -Encoding UTF8 -LiteralPath $campaignPath | ConvertFrom-Json
if ([datetimeoffset]$data.provider_snapshot.expires_at -le [datetimeoffset]::Now) { throw 'Campaign provider snapshot expired.' }
$stageData = @($data.stages | Where-Object id -eq $Stage)[0]
if ($stageData.status -notin @('approved', 'running')) { throw "Stage '$Stage' requires explicit approval." }
$stagePending = @($data.runs | Where-Object { $_.stage -eq $Stage -and $_.status -eq 'pending' })
if (-not $stagePending.Count) { throw 'No pending runs remain in this stage.' }

# Canary rule enforcement (static plan gate, evaluated before any provider
# machinery): a canary fixture executes at most ONE run in its first stage, and
# no run in any later stage, until a canary run-record exists with
# outcome_valid=true and at least 2 distinct grader check dimensions.
. (Join-Path $PSScriptRoot 'fixture-admission.ps1')
$stageOrder = @($data.stages | ForEach-Object { [string]$_.id })
$executable = @()
$canaryBlocked = @()
$canaryScheduled = @{}
foreach ($entry in $stagePending) {
    $isCanary = ($entry.PSObject.Properties.Name -contains 'canary') -and [bool]$entry.canary
    if (-not $isCanary) { $executable += $entry; continue }
    if (Test-CanaryRecordSatisfied -RootPath $rootPath -Campaign $data -FixtureId ([string]$entry.fixture)) { $executable += $entry; continue }
    $fixtureStages = @($data.runs | Where-Object { $_.fixture -eq $entry.fixture } | ForEach-Object { [string]$_.stage } | Sort-Object -Unique)
    $firstStage = @($stageOrder | Where-Object { $_ -in $fixtureStages })[0]
    if ([string]$entry.stage -ne $firstStage) {
        $canaryBlocked += [pscustomobject]@{ run_key = $entry.run_key; fixture = [string]$entry.fixture; reason = 'later-stage-requires-validated-canary-record' }
        continue
    }
    $priorAttempts = @($data.runs | Where-Object { $_.fixture -eq $entry.fixture -and $_.run_id }).Count
    if ($priorAttempts -gt 0 -or $canaryScheduled.ContainsKey([string]$entry.fixture)) {
        $canaryBlocked += [pscustomobject]@{ run_key = $entry.run_key; fixture = [string]$entry.fixture; reason = 'canary-cap-one-stage1-run-per-fixture' }
        continue
    }
    $canaryScheduled[[string]$entry.fixture] = $true
    $executable += $entry
}
if (-not $executable.Count) {
    $blockedFixtures = (@($canaryBlocked | ForEach-Object { $_.fixture } | Sort-Object -Unique) -join ', ')
    throw "Canary gate refused every pending run in stage '$Stage' (fixtures: $blockedFixtures). A canary fixture may proceed only after its single first-stage canary run is graded with outcome_valid=true and at least 2 distinct grader check dimensions. Inspect Evals/runs/<run_id>/run-record.json for the canary attempt, or revalidate the fixture with Evals/validate-outcome-harness.ps1 -Fixture <id>."
}
$pending = @($executable | Select-Object -First $MaxRunsThisInvocation)

$doctorRaw = & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $rootPath 'Setup/bootstrap/doctor-agenticbench.ps1') -Root $rootPath 2>&1 | Out-String
if ($LASTEXITCODE -ne 0) { throw 'AgenticBench doctor is not green; no provider run was started.' }
$doctor = $doctorRaw | ConvertFrom-Json
if (-not $doctor.ready) { throw 'AgenticBench is not ready.' }

$consecutiveFailures = 0
$noProgress = 0
$executed = 0
foreach ($entry in $pending) {
    if (Test-Path -LiteralPath $stopPath) { $data.status = 'stopped-by-kill-switch'; break }
    if ($consecutiveFailures -ge [int]$data.loop.max_consecutive_failures) { $data.status = 'stopped-after-failures'; break }
    if ($noProgress -ge [int]$data.loop.max_no_progress) { $data.status = 'stopped-after-no-progress'; break }

    $provider = @($data.provider_snapshot.providers | Where-Object id -eq $entry.provider)[0]
    $preparedRaw = & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $rootPath 'Evals/tools/new-run.ps1') `
        -Fixture $entry.fixture -Arm $entry.arm -Provider "$($entry.provider)-agenticbench" `
        -ModelProfile 'benchmark-snapshot' -Trial $entry.trial -Isolation dedicated-wsl | Out-String
    $prepared = $preparedRaw | ConvertFrom-Json
    $entry.run_id = $prepared.run_id
    $entry.status = 'running'
    $stageData.status = 'running'
    $data.status = "${Stage}-running"
    $data | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 -LiteralPath $campaignPath

    $old = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $rootPath 'Evals/adapters/providers/invoke-agenticbench.ps1') `
        -Run $entry.run_id -Provider $entry.provider -Model $provider.model -Effort $provider.effort `
        -MaxTurns $data.loop.max_turns_per_run -MaxWallMinutes $data.loop.max_wall_minutes_per_run -Execute | Out-Null
    $providerExit = $LASTEXITCODE
    $ErrorActionPreference = $old

    if ($providerExit -ne 0) {
        $entry.status = 'provider_failed'
        $consecutiveFailures++
        $noProgress++
    } else {
        $executionPath = Join-Path $rootPath "Evals/runs/$($entry.run_id)/provider-execution.json"
        $execution = Get-Content -Raw -Encoding UTF8 -LiteralPath $executionPath | ConvertFrom-Json
        $actualModel = if ($execution.actual_model) { [string]$execution.actual_model } else { 'unresolved-provider-default' }
        $ErrorActionPreference = 'Continue'
        & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $rootPath 'Evals/tools/grade-run.ps1') `
            -Run $entry.run_id -ActualModel $actualModel -Effort $provider.effort | Out-Null
        $gradeExit = $LASTEXITCODE
        $ErrorActionPreference = $old
        $recordPath = Join-Path $rootPath "Evals/runs/$($entry.run_id)/run-record.json"
        $record = if (Test-Path -LiteralPath $recordPath) { Get-Content -Raw $recordPath | ConvertFrom-Json } else { $null }
        $entry.status = if ($gradeExit -ne 0 -or -not $record -or -not [bool]$record.outcome_valid) { 'grading_failed' } elseif ([bool]$record.quality_passed) { 'passed' } else { 'scored' }
        $changed = if ($record) { @($record.changed_files).Count } else { 0 }
        if ($changed -eq 0) { $noProgress++ } else { $noProgress = 0 }
        if ($gradeExit -eq 0) { $consecutiveFailures = 0 } else { $consecutiveFailures++ }
    }
    $executed++
    $data | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 -LiteralPath $campaignPath
}

$remaining = @($data.runs | Where-Object { $_.stage -eq $Stage -and $_.status -eq 'pending' }).Count
if ($remaining -eq 0) {
    $stageData.status = 'complete'
    $next = switch ($Stage) { 'smoke' { 'directional' } 'directional' { 'confidence' } 'confidence' { 'pilot' } 'battery-sentinel' { 'battery-diversity' } default { $null } }
    $data.status = if ($next) { "awaiting-${next}-approval" } else { 'complete' }
}
$data | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 -LiteralPath $campaignPath
$campaignLock.Dispose()
[ordered]@{ campaign_id = $data.campaign_id; stage = $Stage; executed = $executed; remaining = $remaining; canary_blocked = $canaryBlocked.Count; status = $data.status; consecutive_failures = $consecutiveFailures; no_progress = $noProgress } | ConvertTo-Json
