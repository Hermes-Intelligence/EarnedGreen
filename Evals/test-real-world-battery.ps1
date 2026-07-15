[CmdletBinding()]
param([string]$Root)

$ErrorActionPreference = 'Stop'
if (-not $Root) { $Root = Split-Path -Parent $PSScriptRoot }
$rootPath = (Resolve-Path -LiteralPath $Root).Path
$temp = Join-Path ([IO.Path]::GetTempPath()) ('battery-lifecycle-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $temp | Out-Null
$results = @()

function Check([string]$Id, [bool]$Passed, [string]$Evidence) {
    $script:results += [pscustomobject]@{ id = $Id; passed = $Passed; evidence = $Evidence }
}

try {
    $settingsPath = Join-Path $temp 'provider-settings.json'
    [ordered]@{
        schema_version = 1
        generated_at = [datetimeoffset]::Now.ToString('o')
        expires_at = [datetimeoffset]::Now.AddDays(7).ToString('o')
        distro = 'AgenticBench-test'
        providers = @(
            [ordered]@{ id = 'codex'; model = 'explicit-test-model'; effort = 'medium'; cli_version = 'test-only' }
        )
        note = 'Synthetic local lifecycle input; never used for provider execution.'
    } | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 -LiteralPath $settingsPath

    # Fixture admission setup: creation and stage approval both require a fresh
    # outcome-harness validity record per battery fixture. Produce any missing
    # record the honest way by running the harness for that fixture.
    . (Join-Path $rootPath 'Evals/tools/fixture-admission.ps1')
    $batteryProtocol = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $rootPath 'Evals/baselines/real-world-battery-protocol.json') | ConvertFrom-Json
    foreach ($fixtureId in @($batteryProtocol.fixtures.id)) {
        if (-not (Get-FreshFixtureValidityRecord -RootPath $rootPath -FixtureId $fixtureId)) {
            & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $rootPath 'Evals/validate-outcome-harness.ps1') -Fixture $fixtureId | Out-Null
        }
    }

    $raw = & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $rootPath 'Evals/tools/new-real-world-battery-screen.ps1') -Root $rootPath -ProviderSettings $settingsPath -OutputRoot $temp | Out-String
    $created = $raw | ConvertFrom-Json
    $campaignPath = Join-Path $created.path 'campaign.json'
    $campaign = Get-Content -Raw -Encoding UTF8 -LiteralPath $campaignPath | ConvertFrom-Json

    Check 'exact-call-plan' (@($campaign.runs).Count -eq 12 -and @($campaign.runs.run_key | Sort-Object -Unique).Count -eq 12) '12 unique scheduled task-arm cells'
    Check 'staged-six-plus-six' (@($campaign.runs | Where-Object stage -eq 'battery-sentinel').Count -eq 6 -and @($campaign.runs | Where-Object stage -eq 'battery-diversity').Count -eq 6) '6 sentinel and 6 diversity calls'
    Check 'six-families-two-arms' (@($campaign.runs.fixture | Sort-Object -Unique).Count -eq 6 -and @($campaign.runs.arm | Sort-Object -Unique).Count -eq 2) 'six fixtures across vanilla and full arms'
    Check 'zero-call-initial-state' (@($campaign.runs | Where-Object run_id).Count -eq 0 -and @($campaign.stages | Where-Object approved_at).Count -eq 0) 'no run IDs and no approvals after generation'
    Check 'bounded-loop' ($campaign.loop.max_total_runs -eq 12 -and $campaign.loop.max_infrastructure_replacements -eq 0 -and $campaign.loop.max_runs_per_invocation -eq 6) '12 total, 6 per invocation, zero replacements'
    $hashDrift = @($campaign.controls.harness_snapshot | Where-Object { (Get-FileHash -LiteralPath (Join-Path $rootPath $_.path) -Algorithm SHA256).Hash -ne $_.sha256 })
    Check 'pinned-harness' (@($campaign.controls.harness_snapshot).Count -eq 13 -and $hashDrift.Count -eq 0) '13 current pinned hashes'

    $oldPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $rootPath 'Evals/tools/approve-benchmark-stage.ps1') -Root $rootPath -Campaign $created.path -Stage battery-diversity -ApprovedBy lifecycle-negative-control 2>&1 | Out-Null
    $earlyExit = $LASTEXITCODE
    $ErrorActionPreference = $oldPreference
    $afterRejected = Get-Content -Raw -Encoding UTF8 -LiteralPath $campaignPath | ConvertFrom-Json
    Check 'later-stage-fails-closed' ($earlyExit -ne 0 -and @($afterRejected.stages | Where-Object approved_at).Count -eq 0 -and @($afterRejected.runs | Where-Object run_id).Count -eq 0) 'diversity approval rejected before sentinel and no provider state created'

    $approvedRaw = & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $rootPath 'Evals/tools/approve-benchmark-stage.ps1') -Root $rootPath -Campaign $created.path -Stage battery-sentinel -ApprovedBy lifecycle-positive-control | Out-String
    $approvedExit = $LASTEXITCODE
    $approved = if ($approvedExit -eq 0) { $approvedRaw | ConvertFrom-Json } else { $null }
    $afterApproved = Get-Content -Raw -Encoding UTF8 -LiteralPath $campaignPath | ConvertFrom-Json
    Check 'sentinel-approval-only' ($approvedExit -eq 0 -and $approved.runs -eq 6 -and @($afterApproved.stages | Where-Object { $_.id -eq 'battery-sentinel' -and $_.status -eq 'approved' }).Count -eq 1 -and @($afterApproved.stages | Where-Object { $_.id -eq 'battery-diversity' -and $_.status -eq 'awaiting-approval' }).Count -eq 1) 'only the first six-call stage becomes approved'
    Check 'approval-starts-zero-calls' (@($afterApproved.runs | Where-Object run_id).Count -eq 0 -and -not (Get-ChildItem -Recurse -File -LiteralPath $temp | Where-Object Name -eq 'provider-execution.json')) 'approval alone starts no provider process'
} finally {
    if (Test-Path -LiteralPath $temp) { Remove-Item -LiteralPath $temp -Recurse -Force }
}

$failed = @($results | Where-Object { -not $_.passed }).Count
[ordered]@{ schema_version = 1; cases = $results.Count; passed = $results.Count - $failed; failed = $failed; results = $results } | ConvertTo-Json -Depth 7
if ($failed) { exit 1 }
