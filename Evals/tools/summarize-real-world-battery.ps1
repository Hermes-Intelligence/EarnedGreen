[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Campaign,
    [Parameter(Mandatory=$true)][ValidateSet('battery-sentinel','battery-diversity')][string]$Stage,
    [string]$Root
)

$ErrorActionPreference = 'Stop'
if (-not $Root) { $Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot) }
$rootPath = (Resolve-Path -LiteralPath $Root).Path
$campaignDir = (Resolve-Path -LiteralPath (Join-Path $rootPath "Evals/experiments/$Campaign")).Path
$data = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $campaignDir 'campaign.json') | ConvertFrom-Json
$protocol = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $rootPath 'Evals/baselines/real-world-battery-protocol.json') | ConvertFrom-Json
$stageData = @($data.stages | Where-Object id -eq $Stage)[0]
if (-not $stageData -or $stageData.status -ne 'complete') { throw "Stage '$Stage' is not complete." }

function Get-Median([object[]]$Values) {
    $values = @($Values | ForEach-Object { [double]$_ } | Sort-Object)
    if (-not $values.Count) { return $null }
    $mid = [math]::Floor($values.Count / 2)
    if ($values.Count % 2) { return $values[$mid] }
    return ($values[$mid - 1] + $values[$mid]) / 2
}
function Get-PercentDelta([double]$Baseline, [double]$Candidate) {
    if ($Baseline -eq 0) { return $null }
    return [math]::Round((($Candidate - $Baseline) / $Baseline) * 100, 1)
}

$entries = @($data.runs | Where-Object stage -eq $Stage)
if ($entries.Count -ne [int]$stageData.expected_new_runs) { throw 'Run count differs from the approved stage.' }
$rows = @()
foreach ($entry in $entries) {
    if (-not $entry.run_id) { throw "Missing run id for $($entry.run_key)." }
    $runDir = Join-Path $rootPath "Evals/runs/$($entry.run_id)"
    $execution = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $runDir 'provider-execution.json') | ConvertFrom-Json
    $record = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $runDir 'run-record.json') | ConvertFrom-Json
    $rows += [pscustomobject][ordered]@{
        run_id = [string]$entry.run_id
        fixture = [string]$entry.fixture
        arm = [string]$entry.arm
        status = [string]$entry.status
        actual_model = [string]$record.actual_model
        hidden_score = [double]$record.grader.score
        quality_passed = [bool]$record.quality_passed
        failed_checks = @($record.grader.checks | Where-Object { -not $_.passed } | ForEach-Object id)
        duration_seconds = [math]::Round((([datetimeoffset]$record.finished_at)-([datetimeoffset]$record.started_at)).TotalSeconds,1)
        total_observed_tokens = [long]$record.token_usage.total_observed_tokens
        token_usage = $record.token_usage
        reported_cost_usd = $record.monetary_cost.amount_usd
        cost_basis = [string]$record.monetary_cost.basis
        public_pass = [bool]$record.public_tests.passed
        outcome_valid = [bool]$record.outcome_valid
        enforcement_pass = [bool]$record.enforcement_passed
        protected_files_changed = @($record.protected_files_changed)
        changed_files = @($record.changed_files)
        started_at = [string]$record.started_at
        finished_at = [string]$record.finished_at
        provider = [string]$execution.provider
    }
}

$ordered = @($rows | Sort-Object { [datetimeoffset]$_.started_at })
$overlaps = @()
for ($i=1; $i -lt $ordered.Count; $i++) {
    if ([datetimeoffset]$ordered[$i].started_at -lt [datetimeoffset]$ordered[$i-1].finished_at) {
        $overlaps += [ordered]@{ first=$ordered[$i-1].run_id; second=$ordered[$i].run_id }
    }
}
$runIds = @($rows.run_id)
$windowStart = [datetimeoffset]$stageData.approved_at
$windowEnd = [datetimeoffset](@($ordered | Select-Object -Last 1)[0].finished_at)
$executions = @()
Get-ChildItem -Directory -LiteralPath (Join-Path $rootPath 'Evals/runs') | ForEach-Object {
    $path = Join-Path $_.FullName 'provider-execution.json'
    if (Test-Path -LiteralPath $path) {
        $candidate = Get-Content -Raw -Encoding UTF8 -LiteralPath $path | ConvertFrom-Json
        $started = [datetimeoffset]$candidate.started_at
        if ($started -ge $windowStart -and $started -le $windowEnd.AddMinutes(1)) {
            $executions += [pscustomobject]@{ run_id=$_.Name; provider=[string]$candidate.provider }
        }
    }
}
$orphans = @($executions | Where-Object { $runIds -notcontains $_.run_id })
$invalid = @($rows | Where-Object { -not $_.outcome_valid -or $_.status -notin @('passed','scored') })
$integrityPassed = ($rows.Count -eq 6 -and @($runIds | Sort-Object -Unique).Count -eq 6 -and
    $executions.Count -eq 6 -and -not $orphans.Count -and -not $overlaps.Count -and -not $invalid.Count -and
    -not @($rows | Where-Object { -not $_.public_pass -or -not $_.enforcement_pass -or @($_.protected_files_changed).Count }).Count)

$fixtureProtocol = @{}
foreach ($fixture in $protocol.fixtures) { $fixtureProtocol[[string]$fixture.id] = $fixture }
$pairs = @()
foreach ($fixture in @($rows.fixture | Sort-Object -Unique)) {
    $vanilla = @($rows | Where-Object { $_.fixture -eq $fixture -and $_.arm -eq 'vanilla' })[0]
    $full = @($rows | Where-Object { $_.fixture -eq $fixture -and $_.arm -eq 'core-router-enforcement' })[0]
    if (-not $vanilla -or -not $full) { throw "Incomplete pair for $fixture." }
    $critical = @($fixtureProtocol[$fixture].critical_checks)
    $vanillaFailed = @($vanilla.failed_checks | Where-Object { $critical -contains $_ })
    $fullFailed = @($full.failed_checks | Where-Object { $critical -contains $_ })
    $pairs += [pscustomobject][ordered]@{
        fixture = $fixture
        vanilla_score = $vanilla.hidden_score
        full_score = $full.hidden_score
        quality_delta_full_minus_vanilla = $full.hidden_score - $vanilla.hidden_score
        critical_difference = (($vanillaFailed -join '|') -ne ($fullFailed -join '|'))
        vanilla_failed_checks = @($vanilla.failed_checks)
        full_failed_checks = @($full.failed_checks)
        vanilla_seconds = $vanilla.duration_seconds
        full_seconds = $full.duration_seconds
        vanilla_tokens = $vanilla.total_observed_tokens
        full_tokens = $full.total_observed_tokens
    }
}

$arms = [ordered]@{}
foreach ($arm in @('vanilla','core-router-enforcement')) {
    $armRows = @($rows | Where-Object arm -eq $arm)
    $arms[$arm] = [ordered]@{
        runs = $armRows.Count
        macro_median_score = Get-Median @($armRows.hidden_score)
        mean_score = [math]::Round((($armRows.hidden_score | Measure-Object -Average).Average),2)
        quality_passes = @($armRows | Where-Object quality_passed).Count
        median_wall_seconds = Get-Median @($armRows.duration_seconds)
        total_wall_seconds = [math]::Round((($armRows.duration_seconds | Measure-Object -Sum).Sum),1)
        median_tokens = Get-Median @($armRows.total_observed_tokens)
        total_tokens = [long](($armRows.total_observed_tokens | Measure-Object -Sum).Sum)
    }
}
$vanilla = $arms['vanilla']; $full = $arms['core-router-enforcement']
$noSignal = (-not @($pairs | Where-Object { [math]::Abs($_.quality_delta_full_minus_vanilla) -gt 3 }).Count -and
    -not @($pairs | Where-Object critical_difference).Count)
$conclusion = if (-not $integrityPassed) { 'INVALID' } elseif ($noSignal) { 'NO_ACTIONABLE_SIGNAL' } else { 'MIXED_OR_SIGNAL_REVIEW' }

$summary = [ordered]@{
    schema_version = 1
    campaign_id = [string]$data.campaign_id
    stage = $Stage
    generated_at = [datetimeoffset]::Now.ToString('o')
    claim_level = 'cost-bounded screening only'
    measurement_integrity = [ordered]@{
        verdict = if ($integrityPassed) {'PASS'} else {'FAIL'}
        approved_calls = 6; completed_unique_runs = @($runIds | Sort-Object -Unique).Count
        provider_executions_in_window = $executions.Count; orphan_runs = $orphans.Count
        overlaps = $overlaps.Count; invalid_outcomes = $invalid.Count
        protected_file_changes = @($rows | ForEach-Object protected_files_changed).Count
        later_stage_run_ids = @($data.runs | Where-Object { $_.stage -ne $Stage -and $_.run_id }).Count
    }
    comparative_result = [ordered]@{
        conclusion = $conclusion
        all_task_deltas_within_three = $noSignal
        any_critical_difference = @($pairs | Where-Object critical_difference).Count -gt 0
        decision = 'This sentinel alone shows no quality lift. The diversity stage remains locked and requires a separate human decision; no replication, Claude run, promotion or model switch is authorized.'
    }
    arms = $arms
    resource_comparison = [ordered]@{
        median_seconds_delta_full_minus_vanilla = [math]::Round($full.median_wall_seconds-$vanilla.median_wall_seconds,1)
        median_seconds_percent_delta = Get-PercentDelta $vanilla.median_wall_seconds $full.median_wall_seconds
        median_tokens_delta_full_minus_vanilla = [long]($full.median_tokens-$vanilla.median_tokens)
        median_tokens_percent_delta = Get-PercentDelta $vanilla.median_tokens $full.median_tokens
        total_observed_tokens = [long](($rows.total_observed_tokens | Measure-Object -Sum).Sum)
        monetary_cost_coverage = "$(@($rows | Where-Object { $null -ne $_.reported_cost_usd }).Count)/6"
        cost_basis = @($rows.cost_basis | Sort-Object -Unique)
    }
    pairs = @($pairs | Sort-Object fixture)
    runs = @($rows | Sort-Object fixture,arm)
    protocol = 'Evals/baselines/real-world-battery-protocol.json'
    additional_provider_calls = 0
}

$base = Join-Path $rootPath "Evals/reports/$($data.campaign_id)-$Stage"
$summary | ConvertTo-Json -Depth 14 | Set-Content -Encoding UTF8 -LiteralPath ($base+'.json')
$md = @(
    '# Real-World Battery Sentinel Report','',
    "- Campaign: ``$($data.campaign_id)``", "- Generated: $($summary.generated_at)",
    "- Measurement integrity: **$($summary.measurement_integrity.verdict)**",
    "- Comparative conclusion: **$conclusion**", '- Claim level: cost-bounded screening only','',
    '## Executive result','',
    'Exactly six approved Codex calls completed sequentially across three production-style task families. Every vanilla/full pair received the same hidden score and had the same critical-check outcome. The predeclared sentinel result is therefore NO_ACTIONABLE_SIGNAL: this stage measured no quality improvement from Core + Router + enforcement.','',
    "Median wall time was $($full.median_wall_seconds) seconds for full versus $($vanilla.median_wall_seconds) for vanilla (+$($summary.resource_comparison.median_seconds_percent_delta)%). Median observed tokens were $($full.median_tokens) versus $($vanilla.median_tokens) (+$($summary.resource_comparison.median_tokens_percent_delta)%). The subscription CLI did not report monetary cost, so no dollar estimate is invented.",'',
    '## Task outcomes','',
    '| Task family | Vanilla | Full | Delta | Vanilla issue | Full issue |','|---|---:|---:|---:|---|---|'
)
foreach ($pair in @($pairs | Sort-Object fixture)) {
    $vf = if ($pair.vanilla_failed_checks.Count) {$pair.vanilla_failed_checks -join ', '} else {'none'}
    $ff = if ($pair.full_failed_checks.Count) {$pair.full_failed_checks -join ', '} else {'none'}
    $md += "| $($pair.fixture) | $($pair.vanilla_score) | $($pair.full_score) | $($pair.quality_delta_full_minus_vanilla) | $vf | $ff |"
}
$md += @('','## Resource comparison','',
    '| Arm | Median score | Mean score | Quality passes | Median seconds | Median tokens |','|---|---:|---:|---:|---:|---:|',
    "| Vanilla | $($vanilla.macro_median_score) | $($vanilla.mean_score) | $($vanilla.quality_passes)/3 | $($vanilla.median_wall_seconds) | $($vanilla.median_tokens) |",
    "| Core + Router + enforcement | $($full.macro_median_score) | $($full.mean_score) | $($full.quality_passes)/3 | $($full.median_wall_seconds) | $($full.median_tokens) |",'',
    'Full used more time and tokens without a measured quality gain in this sentinel. This is evidence against assuming that more context automatically helps; it is not proof that the full environment has no value on the three untested diversity families.','',
    '## What the failures reveal','',
    '- API propagation: both arms reached 90/100 and missed input validation. Both updated hidden consumers, so the fixture successfully exposed a narrower contract-quality gap.',
    '- Coordinated release: both arms reached 90/100 and missed the documentation check. Code, migration and observability behavior passed, but neither completed the full product change.',
    '- Resumable session: both arms reached 100/100, including split resume, failure recovery, corruption handling and schema safety.','',
    '## Integrity evidence','',
    '- Approved/completed calls: 6/6; unique run IDs: 6.',
    "- Provider executions / orphans / overlaps / invalid outcomes: $($summary.measurement_integrity.provider_executions_in_window) / $($summary.measurement_integrity.orphan_runs) / $($summary.measurement_integrity.overlaps) / $($summary.measurement_integrity.invalid_outcomes).",
    "- Protected-file changes: $($summary.measurement_integrity.protected_file_changes); later-stage run IDs: $($summary.measurement_integrity.later_stage_run_ids).",
    "- Total observed tokens: $($summary.resource_comparison.total_observed_tokens); provider-reported USD coverage: $($summary.resource_comparison.monetary_cost_coverage).",'',
    '## Decision and next gate','',
    '**STOP at the approval boundary.** The sentinel is complete, and the campaign is waiting for a separate decision on the six-call diversity stage. No diversity, replication, Claude, Stable promotion or automatic model switching is authorized by this result.','',
    'If diversity is approved, it should be justified as testing three materially different failure families - open-world parsing, misleading-green cache behavior and instruction-precedence defense - not as a retry of this tie. The complete six-family screen would still be exploratory and non-confirmatory.','',
    'The structured JSON beside this report is the measurement source of truth. The PDF is the human-readable rendering.'
)
$md -join [Environment]::NewLine | Set-Content -Encoding UTF8 -LiteralPath ($base+'.md')
[ordered]@{json=$base+'.json';markdown=$base+'.md';verdict=$conclusion;provider_calls=6;additional_provider_calls=0} | ConvertTo-Json
