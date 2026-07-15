[CmdletBinding()]
param(
    [int]$Seed = 20260713,
    [string]$ProviderSettings,
    [string]$Root
)

$ErrorActionPreference = 'Stop'
if (-not $Root) { $Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot) }
$rootPath = (Resolve-Path -LiteralPath $Root).Path
if (-not $ProviderSettings) { $ProviderSettings = Join-Path $rootPath 'Evals/local/provider-settings.json' }
if (-not (Test-Path -LiteralPath $ProviderSettings)) { throw 'Local provider settings are missing. Run refresh-local-provider-settings.ps1.' }
$settings = Get-Content -Raw -Encoding UTF8 -LiteralPath $ProviderSettings | ConvertFrom-Json
if ([datetimeoffset]$settings.expires_at -le [datetimeoffset]::Now) { throw 'Local provider settings expired; refresh them before creating a campaign.' }
$providers = @($settings.providers.id)
if (@($providers | Sort-Object -Unique).Count -ne 2 -or 'codex' -notin $providers -or 'claude' -notin $providers) { throw 'Campaign requires exactly Codex and Claude provider snapshots.' }

# Fixture admission (pre-spend): every scheduled fixture needs a fresh
# outcome-harness validity record before a paid campaign may be constructed.
. (Join-Path $PSScriptRoot 'fixture-admission.ps1')
$campaignFixtures = @('entity-parser-unseen', 'objective-omission')
Assert-FixtureAdmission -RootPath $rootPath -FixtureIds $campaignFixtures -Context 'campaign creation (pre-spend)'
# Canary rule: zero paid history with outcome_valid=true forces a canary plan.
$canaryFixtures = Get-CanaryFixtures -RootPath $rootPath -FixtureIds $campaignFixtures

$definitions = @(
    [ordered]@{ id = 'smoke'; fixtures = @('entity-parser-unseen'); trials = @(1); expected_new_runs = 4; cumulative_runs = 4 },
    [ordered]@{ id = 'directional'; fixtures = @('objective-omission'); trials = @(1); expected_new_runs = 4; cumulative_runs = 8 },
    [ordered]@{ id = 'confidence'; fixtures = @('entity-parser-unseen', 'objective-omission'); trials = @(2, 3); expected_new_runs = 16; cumulative_runs = 24 },
    [ordered]@{ id = 'pilot'; fixtures = @('entity-parser-unseen', 'objective-omission'); trials = @(4, 5); expected_new_runs = 16; cumulative_runs = 40 }
)
$arms = @('vanilla', 'core-router-enforcement')
$runs = @()
foreach ($stage in $definitions) {
    foreach ($fixture in $stage.fixtures) {
        foreach ($provider in $providers) {
            foreach ($arm in $arms) {
                foreach ($trial in $stage.trials) {
                    $runs += [ordered]@{
                        run_key = "$($stage.id)::$fixture::$provider::$arm::t$trial"
                        stage = $stage.id
                        fixture = $fixture
                        provider = $provider
                        arm = $arm
                        trial = $trial
                        canary = ($fixture -in $canaryFixtures)
                        status = 'pending'
                        run_id = $null
                    }
                }
            }
        }
    }
}
Get-Random -SetSeed $Seed | Out-Null
$runs = @($runs | Sort-Object { Get-Random })
foreach ($stage in $definitions) {
    $actual = @($runs | Where-Object stage -eq $stage.id).Count
    if ($actual -ne $stage.expected_new_runs) { throw "Stage $($stage.id) expected $($stage.expected_new_runs) runs but generated $actual." }
}
if ($runs.Count -ne 40) { throw "Campaign must contain exactly 40 runs; got $($runs.Count)." }

$id = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-subscription-campaign'
$path = Join-Path $rootPath "Evals/experiments/$id"
New-Item -ItemType Directory -Path $path | Out-Null
$harnessFiles = @('Evals/tools/new-run.ps1','Evals/tools/grade-run.ps1','Evals/tools/run-benchmark-stage.ps1','Evals/adapters/providers/invoke-agenticbench.ps1','Evals/fixtures/catalog.json')
$harnessSnapshot = @($harnessFiles | ForEach-Object { [ordered]@{path=$_;sha256=(Get-FileHash -LiteralPath (Join-Path $rootPath $_) -Algorithm SHA256).Hash} })
$campaign = [ordered]@{
    schema_version = 2
    campaign_id = $id
    status = 'awaiting-smoke-approval'
    publishable = $true
    created_at = [datetimeoffset]::Now.ToString('o')
    isolation = 'dedicated-wsl'
    provider_snapshot = $settings
    controls = [ordered]@{
        same_prompt_within_fixture = $true
        same_provider_model_within_campaign = $true
        clean_workspace_per_run = $true
        hidden_graders_host_only = $true
        randomized_order = $true
        randomization_seed = $Seed
        harness_snapshot = $harnessSnapshot
    }
    canary_policy = (New-CanaryPolicy -CanaryFixtures $canaryFixtures)
    loop = [ordered]@{
        objective = 'Measure outcome quality of vanilla versus full agentic guidance for Codex and Claude.'
        non_goals = @('Automatic stable-rule promotion', 'Automatic model switching', 'Unbounded retries')
        completion = 'All approved stage runs graded and summarized.'
        progress_signal = 'A pending run becomes passed, failed, or provider_failed with evidence.'
        max_total_runs = 40
        max_infrastructure_replacements = 2
        max_runs_per_invocation = 4
        max_wall_minutes_per_run = 15
        max_turns_per_run = 12
        max_consecutive_failures = 2
        max_no_progress = 2
        kill_switch = 'Evals/local/STOP'
        escalation = @('Authentication loss', 'Provider or model drift', 'Isolation failure', 'Budget ceiling', 'Two consecutive failures')
    }
    stages = @($definitions | ForEach-Object {
        [ordered]@{ id = $_.id; expected_new_runs = $_.expected_new_runs; cumulative_runs = $_.cumulative_runs; status = 'awaiting-approval'; approved_at = $null; approved_by = $null }
    })
    runs = $runs
}
$campaign | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $path 'campaign.json')
[ordered]@{ campaign_id = $id; path = $path; runs = $runs.Count; first_stage_runs = 4; status = $campaign.status } | ConvertTo-Json -Depth 5
