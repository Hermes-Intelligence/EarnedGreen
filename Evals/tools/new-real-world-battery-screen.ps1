[CmdletBinding()]
param(
    [int]$Seed = 20260713,
    [string]$ProviderSettings,
    [string]$OutputRoot,
    [string]$Root
)

$ErrorActionPreference = 'Stop'
if (-not $Root) { $Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot) }
$rootPath = (Resolve-Path -LiteralPath $Root).Path
if (-not $ProviderSettings) { $ProviderSettings = Join-Path $rootPath 'Evals/local/provider-settings.json' }
if (-not $OutputRoot) { $OutputRoot = Join-Path $rootPath 'Evals/experiments' }
$settings = Get-Content -Raw -Encoding UTF8 -LiteralPath $ProviderSettings | ConvertFrom-Json
if ([datetimeoffset]$settings.expires_at -le [datetimeoffset]::Now) { throw 'Local provider settings expired.' }
$provider = @($settings.providers | Where-Object id -eq 'codex')[0]
if (-not $provider -or $provider.model -eq 'provider-default') { throw 'Battery screen requires an explicit Codex model selector.' }

$protocolPath = Join-Path $rootPath 'Evals/baselines/real-world-battery-protocol.json'
$protocol = Get-Content -Raw -Encoding UTF8 -LiteralPath $protocolPath | ConvertFrom-Json
$catalog = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $rootPath 'Evals/fixtures/catalog.json') | ConvertFrom-Json
$evidencePath = Join-Path $rootPath $protocol.local_evidence.report
$evidence = Get-Content -Raw -Encoding UTF8 -LiteralPath $evidencePath | ConvertFrom-Json
if ($evidence.failed -ne 0 -or $evidence.passed -lt [int]$protocol.local_evidence.required_total_passed) { throw 'Real-world battery local evidence is not green.' }

$fixtureIds = @($protocol.fixtures.id)
if (@($fixtureIds | Sort-Object -Unique).Count -ne 6) { throw 'Battery protocol must contain six unique fixtures.' }
foreach ($fixtureId in $fixtureIds) {
    $fixture = @($catalog.fixtures | Where-Object id -eq $fixtureId)[0]
    $result = @($evidence.results | Where-Object id -eq $fixtureId)[0]
    if (-not $fixture -or @($fixture.negative_controls).Count -lt 2 -or -not $result.passed -or [double]$result.reference_score -ne 100) {
        throw "Fixture '$fixtureId' has incomplete discrimination evidence."
    }
}
if ((@($protocol.fixtures | ForEach-Object { @((@($catalog.fixtures | Where-Object id -eq $_.id)[0]).negative_controls).Count } | Measure-Object -Sum).Sum) -lt [int]$protocol.local_evidence.required_negative_controls) {
    throw 'Battery negative-control evidence is incomplete.'
}

# Fixture admission (pre-spend): each battery fixture needs a fresh
# outcome-harness validity record before the paid plan may be constructed.
. (Join-Path $PSScriptRoot 'fixture-admission.ps1')
Assert-FixtureAdmission -RootPath $rootPath -FixtureIds $fixtureIds -Context 'battery screen creation (pre-spend)'
# Canary rule: zero paid history with outcome_valid=true forces a canary plan.
$canaryFixtures = Get-CanaryFixtures -RootPath $rootPath -FixtureIds $fixtureIds

$runs = @()
foreach ($fixture in $protocol.fixtures) {
    foreach ($arm in $protocol.arms) {
        $runs += [ordered]@{
            run_key = "$($fixture.stage)::$($fixture.id)::codex::$arm::t1"
            stage = [string]$fixture.stage
            fixture = [string]$fixture.id
            provider = 'codex'
            arm = [string]$arm
            trial = 1
            grader_seed = 20260714
            canary = ([string]$fixture.id -in $canaryFixtures)
            status = 'pending'
            run_id = $null
        }
    }
}
Get-Random -SetSeed $Seed | Out-Null
$runs = @($runs | Sort-Object { Get-Random })
$harnessFiles = @(
    'Evals/tools/new-run.ps1',
    'Evals/tools/grade-run.ps1',
    'Evals/tools/run-benchmark-stage.ps1',
    'Evals/adapters/providers/invoke-agenticbench.ps1',
    'Evals/tools/read-provider-telemetry.ps1',
    'Evals/fixtures/catalog.json',
    'Evals/baselines/real-world-battery-protocol.json'
) + @($fixtureIds | ForEach-Object { "Evals/fixtures/$_/hidden/grade.py" })
$harnessSnapshot = @($harnessFiles | ForEach-Object { [ordered]@{ path = $_; sha256 = (Get-FileHash -LiteralPath (Join-Path $rootPath $_) -Algorithm SHA256).Hash } })

$id = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-real-world-battery-screen'
$path = Join-Path $OutputRoot $id
New-Item -ItemType Directory -Path $path | Out-Null
$campaign = [ordered]@{
    schema_version = 2
    campaign_id = $id
    campaign_kind = 'real-world-battery-screen'
    status = 'awaiting-battery-sentinel-approval'
    publishable = $false
    created_at = [datetimeoffset]::Now.ToString('o')
    isolation = 'dedicated-wsl'
    provider_snapshot = $settings
    canary_policy = (New-CanaryPolicy -CanaryFixtures $canaryFixtures)
    controls = [ordered]@{
        screening_only = $true
        explicit_model_required = $true
        clean_workspace_per_run = $true
        hidden_graders_host_only = $true
        randomized_order = $true
        randomization_seed = $Seed
        task_families = 6
        harness_snapshot = $harnessSnapshot
        local_evidence = $protocol.local_evidence.report
    }
    decision_rule = $protocol.outcomes
    loop = [ordered]@{
        objective = $protocol.objective
        non_goals = @('Publication', 'Stable promotion', 'Claude execution', 'Automatic confirmation', 'Automatic retries', 'Automatic model switching')
        completion = 'Each separately approved six-call stage completes or stops safely.'
        progress_signal = 'A pending task-arm cell receives a retained scored or invalid disposition.'
        max_total_runs = 12
        max_infrastructure_replacements = 0
        max_runs_per_invocation = 6
        max_wall_minutes_per_run = 20
        max_turns_per_run = 16
        max_consecutive_failures = 2
        max_no_progress = 2
        kill_switch = 'Evals/local/STOP'
        escalation = @('Any extra-call requirement', 'Authentication loss', 'Isolation drift', 'Provider/model drift', 'Harness hash drift', 'Protected-file drift')
    }
    stages = @(
        [ordered]@{ id = 'battery-sentinel'; expected_new_runs = 6; cumulative_runs = 6; status = 'awaiting-approval'; approved_at = $null; approved_by = $null },
        [ordered]@{ id = 'battery-diversity'; expected_new_runs = 6; cumulative_runs = 12; status = 'awaiting-approval'; approved_at = $null; approved_by = $null }
    )
    runs = $runs
}
$campaign | ConvertTo-Json -Depth 14 | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $path 'campaign.json')
[ordered]@{ schema_version = 1; campaign_id = $id; path = $path; provider = 'codex'; model = $provider.model; sentinel_calls = 6; diversity_calls = 6; total_calls = 12; status = $campaign.status; additional_provider_calls = 0 } | ConvertTo-Json -Depth 6
