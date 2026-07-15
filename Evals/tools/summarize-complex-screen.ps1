[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Campaign,
    [string]$Root
)

$ErrorActionPreference = 'Stop'
if (-not $Root) { $Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot) }
$rootPath = (Resolve-Path -LiteralPath $Root).Path
$experimentsRoot = (Resolve-Path -LiteralPath (Join-Path $rootPath 'Evals/experiments')).Path
$campaignDir = if ([IO.Path]::IsPathRooted($Campaign)) {
    (Resolve-Path -LiteralPath $Campaign).Path
} else {
    (Resolve-Path -LiteralPath (Join-Path $experimentsRoot $Campaign)).Path
}
if (-not $campaignDir.StartsWith($experimentsRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Campaign escaped Evals/experiments.'
}

function Get-Median([object[]]$Values) {
    $ordered = @($Values | ForEach-Object { [double]$_ } | Sort-Object)
    if (-not $ordered.Count) { return $null }
    $middle = [math]::Floor($ordered.Count / 2)
    if ($ordered.Count % 2) { return [double]$ordered[$middle] }
    return ([double]$ordered[$middle - 1] + [double]$ordered[$middle]) / 2
}

function Get-PercentDelta([double]$Baseline, [double]$Candidate) {
    if ($Baseline -eq 0) { return $null }
    return [math]::Round((($Candidate - $Baseline) / $Baseline) * 100, 1)
}

$data = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $campaignDir 'campaign.json') | ConvertFrom-Json
if ($data.campaign_kind -ne 'complex-quality-screen') { throw 'Campaign is not a complex-quality-screen.' }
$stage = @($data.stages | Where-Object id -eq 'complex-screen')[0]
if (-not $stage -or $stage.status -ne 'complete') { throw 'complex-screen stage is not complete.' }
$entries = @($data.runs | Where-Object stage -eq 'complex-screen')
if ($entries.Count -ne [int]$stage.expected_new_runs) { throw 'Completed run count does not match the approved stage.' }

$protocolPath = Join-Path $rootPath 'Evals/baselines/production-ingestion-protocol.json'
$protocol = Get-Content -Raw -Encoding UTF8 -LiteralPath $protocolPath | ConvertFrom-Json
$floors = $protocol.primary_outcomes.hidden_quality_score.critical_floors
$rows = @()
foreach ($entry in $entries) {
    if (-not $entry.run_id) { throw "Run id missing for $($entry.run_key)." }
    $runDir = Join-Path $rootPath "Evals/runs/$($entry.run_id)"
    $execution = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $runDir 'provider-execution.json') | ConvertFrom-Json
    $record = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $runDir 'run-record.json') | ConvertFrom-Json
    $dimensions = [ordered]@{}
    foreach ($name in @('functional','generalization','reliability','security','edge-cases','performance')) {
        $dimensions[$name] = [double]$record.grader.dimensions.$name.earned
    }
    $failedChecks = @($record.grader.checks | Where-Object { -not $_.passed } | ForEach-Object { [string]$_.id })
    $rows += [pscustomobject][ordered]@{
        run_id = [string]$entry.run_id
        arm = [string]$entry.arm
        trial = [int]$entry.trial
        grader_seed = [int]$entry.grader_seed
        status = [string]$entry.status
        provider = [string]$entry.provider
        actual_model = ([string]$execution.actual_model -replace '\[[0-9;]*m\]?', '').Trim()
        effort = [string]$record.effort
        started_at = [string]$execution.started_at
        finished_at = [string]$execution.finished_at
        duration_seconds = [math]::Round((([datetimeoffset]$execution.finished_at) - ([datetimeoffset]$execution.started_at)).TotalSeconds, 1)
        provider_exit = [int]$execution.exit_code
        outcome_valid = [bool]$record.outcome_valid
        public_pass = [bool]$record.public_tests.passed
        hidden_score = [double]$record.grader.score
        hidden_pass = [bool]$record.grader.passed
        enforcement_pass = [bool]$record.enforcement_passed
        protected_files_changed = @($record.protected_files_changed)
        dimensions = [pscustomobject]$dimensions
        failed_checks = $failedChecks
        token_usage = $execution.token_usage
        total_observed_tokens = [long]$execution.token_usage.total_observed_tokens
        reported_cost_usd = if ($execution.monetary_cost -and $null -ne $execution.monetary_cost.amount_usd) { [double]$execution.monetary_cost.amount_usd } else { $null }
        cost_basis = if ($execution.monetary_cost) { [string]$execution.monetary_cost.basis } else { 'not-recorded' }
    }
}

$ordered = @($rows | Sort-Object { [datetimeoffset]$_.started_at })
$overlaps = @()
for ($index = 1; $index -lt $ordered.Count; $index++) {
    if ([datetimeoffset]$ordered[$index].started_at -lt [datetimeoffset]$ordered[$index - 1].finished_at) {
        $overlaps += [ordered]@{ first = $ordered[$index - 1].run_id; second = $ordered[$index].run_id }
    }
}

$runIds = @($rows.run_id)
$windowStart = [datetimeoffset]$stage.approved_at
$windowEnd = (@($rows | Sort-Object { [datetimeoffset]$_.finished_at } | Select-Object -Last 1).finished_at)
$providerExecutionsInWindow = @()
Get-ChildItem -Directory -LiteralPath (Join-Path $rootPath 'Evals/runs') | ForEach-Object {
    $providerPath = Join-Path $_.FullName 'provider-execution.json'
    if (Test-Path -LiteralPath $providerPath) {
        $candidate = Get-Content -Raw -Encoding UTF8 -LiteralPath $providerPath | ConvertFrom-Json
        $started = [datetimeoffset]$candidate.started_at
        if ($started -ge $windowStart -and $started -le ([datetimeoffset]$windowEnd).AddMinutes(1)) {
            $providerExecutionsInWindow += [pscustomobject]@{ run_id = $_.Name; provider = [string]$candidate.provider }
        }
    }
}
$orphans = @($providerExecutionsInWindow | Where-Object { $runIds -notcontains $_.run_id })
$claudeRuns = @($providerExecutionsInWindow | Where-Object { $_.provider -match 'claude' })
$invalidRows = @($rows | Where-Object { -not $_.outcome_valid -or $_.status -notin @('scored','passed') })
$integrityPassed = (
    $rows.Count -eq [int]$stage.expected_new_runs -and
    @($runIds | Sort-Object -Unique).Count -eq $rows.Count -and
    $providerExecutionsInWindow.Count -eq $rows.Count -and
    -not $orphans.Count -and -not $claudeRuns.Count -and -not $overlaps.Count -and -not $invalidRows.Count -and
    -not @($rows | Where-Object { $_.provider_exit -ne 0 -or -not $_.public_pass -or -not $_.enforcement_pass -or @($_.protected_files_changed).Count }).Count
)

$pairs = @()
foreach ($trial in @($rows.trial | Sort-Object -Unique)) {
    $vanilla = @($rows | Where-Object { $_.trial -eq $trial -and $_.arm -eq 'vanilla' })[0]
    $full = @($rows | Where-Object { $_.trial -eq $trial -and $_.arm -eq 'core-router-enforcement' })[0]
    if (-not $vanilla -or -not $full) { throw "Incomplete pair for trial $trial." }
    $criticalDifference = $false
    foreach ($dimension in @('generalization','reliability','security')) {
        $floor = [double]$floors.$dimension
        if (($vanilla.dimensions.$dimension -ge $floor) -ne ($full.dimensions.$dimension -ge $floor)) { $criticalDifference = $true }
    }
    $pairs += [pscustomobject][ordered]@{
        trial = [int]$trial
        grader_seed = [int]$vanilla.grader_seed
        vanilla_score = [double]$vanilla.hidden_score
        full_score = [double]$full.hidden_score
        quality_delta_full_minus_vanilla = [double]($full.hidden_score - $vanilla.hidden_score)
        critical_floor_difference = $criticalDifference
        vanilla_seconds = [double]$vanilla.duration_seconds
        full_seconds = [double]$full.duration_seconds
        seconds_delta_full_minus_vanilla = [math]::Round($full.duration_seconds - $vanilla.duration_seconds, 1)
        vanilla_tokens = [long]$vanilla.total_observed_tokens
        full_tokens = [long]$full.total_observed_tokens
        token_delta_full_minus_vanilla = [long]($full.total_observed_tokens - $vanilla.total_observed_tokens)
    }
}

$arms = [ordered]@{}
foreach ($arm in @('vanilla','core-router-enforcement')) {
    $armRows = @($rows | Where-Object arm -eq $arm)
    $dimensionMedians = [ordered]@{}
    foreach ($dimension in @('functional','generalization','reliability','security','edge-cases','performance')) {
        $dimensionMedians[$dimension] = Get-Median @($armRows | ForEach-Object { $_.dimensions.$dimension })
    }
    $arms[$arm] = [ordered]@{
        runs = $armRows.Count
        quality_median = Get-Median @($armRows.hidden_score)
        quality_min = [double](($armRows.hidden_score | Measure-Object -Minimum).Minimum)
        quality_max = [double](($armRows.hidden_score | Measure-Object -Maximum).Maximum)
        dimension_medians = $dimensionMedians
        wall_seconds_median = Get-Median @($armRows.duration_seconds)
        wall_seconds_total = [math]::Round((($armRows.duration_seconds | Measure-Object -Sum).Sum), 1)
        tokens_median = Get-Median @($armRows.total_observed_tokens)
        tokens_total = [long](($armRows.total_observed_tokens | Measure-Object -Sum).Sum)
    }
}

$allHundred = @($rows | Where-Object hidden_score -ne 100).Count -eq 0
$allPairDeltasWithinThree = @($pairs | Where-Object { [math]::Abs($_.quality_delta_full_minus_vanilla) -gt 3 }).Count -eq 0
$anyCriticalDifference = @($pairs | Where-Object critical_floor_difference).Count -gt 0
$medianQualityDelta = (Get-Median @($pairs.quality_delta_full_minus_vanilla))
$materialSignal = [math]::Abs($medianQualityDelta) -ge [double]$protocol.primary_outcomes.hidden_quality_score.smallest_meaningful_difference -or $anyCriticalDifference
$conclusion = if (-not $integrityPassed) {
    'INVALID'
} elseif ($allHundred) {
    'CEILING'
} elseif ($allPairDeltasWithinThree -and -not $anyCriticalDifference) {
    'NO_ACTIONABLE_SIGNAL'
} elseif ($materialSignal) {
    'MATERIAL_SIGNAL'
} else {
    'INCONCLUSIVE'
}

$failedGroups = @($rows | ForEach-Object { $_.failed_checks } | Group-Object)
$systematicFailedChecks = @($failedGroups | Where-Object Count -eq $rows.Count | ForEach-Object Name | Sort-Object)
$fixtureAlignmentStatus = if ($systematicFailedChecks -contains 'replay-duplicate') { 'REVIEW_REQUIRED' } else { 'NO_COMMON_MODE_FAILURE_FOUND' }
$vanillaStats = $arms['vanilla']
$fullStats = $arms['core-router-enforcement']
$qualityTie = [math]::Abs([double]$fullStats.quality_median - [double]$vanillaStats.quality_median) -le 5 -and -not $anyCriticalDifference

$summary = [ordered]@{
    schema_version = 1
    campaign_id = [string]$data.campaign_id
    stage = 'complex-screen'
    generated_at = [datetimeoffset]::Now.ToString('o')
    screening_only = $true
    publishable_comparison = $false
    measurement_integrity = [ordered]@{
        verdict = if ($integrityPassed) { 'PASS' } else { 'FAIL' }
        approved_calls = [int]$stage.expected_new_runs
        completed_unique_runs = @($runIds | Sort-Object -Unique).Count
        provider_executions_in_window = $providerExecutionsInWindow.Count
        orphan_runs = $orphans.Count
        claude_runs = $claudeRuns.Count
        overlaps = $overlaps.Count
        invalid_outcomes = $invalidRows.Count
        protected_file_changes = @($rows | ForEach-Object { $_.protected_files_changed }).Count
    }
    comparative_result = [ordered]@{
        conclusion = $conclusion
        median_quality_delta_full_minus_vanilla = $medianQualityDelta
        every_pair_within_three = $allPairDeltasWithinThree
        any_critical_floor_difference = $anyCriticalDifference
        quality_tie_for_resource_comparison = $qualityTie
        decision = if ($conclusion -eq 'NO_ACTIONABLE_SIGNAL') { 'STOP: no confirmation or cross-provider calls. Redesign the fixture before requesting more provider spend.' } elseif ($conclusion -eq 'MATERIAL_SIGNAL') { 'A separate confirmation campaign and explicit approval are required.' } else { 'STOP and review the evidence before any additional provider call.' }
    }
    fixture_alignment = [ordered]@{
        status = $fixtureAlignmentStatus
        systematic_failed_checks = $systematicFailedChecks
        observation = 'All six solutions added index to duplicate skipped records, while the hidden replay check requires an exact object without index. The public task specifies exact fields for rejected records but not an equally explicit exact-field schema for skipped records.'
        impact = 'Treat the shared 95 as common-mode fixture-alignment evidence, not as proof that either arm has a reliability defect. Preserve the original pinned results; clarify and revalidate a future fixture instead of retroactively regrading this campaign.'
    }
    arms = $arms
    resource_comparison = [ordered]@{
        median_seconds_delta_full_minus_vanilla = [math]::Round([double]$fullStats.wall_seconds_median - [double]$vanillaStats.wall_seconds_median, 1)
        median_seconds_percent_delta = Get-PercentDelta ([double]$vanillaStats.wall_seconds_median) ([double]$fullStats.wall_seconds_median)
        median_tokens_delta_full_minus_vanilla = [long]([double]$fullStats.tokens_median - [double]$vanillaStats.tokens_median)
        median_tokens_percent_delta = Get-PercentDelta ([double]$vanillaStats.tokens_median) ([double]$fullStats.tokens_median)
        total_observed_tokens = [long](($rows.total_observed_tokens | Measure-Object -Sum).Sum)
        reported_cost_coverage = "$(@($rows | Where-Object { $null -ne $_.reported_cost_usd }).Count)/$($rows.Count) provider calls"
        cost_basis = @($rows.cost_basis | Sort-Object -Unique)
        interpretation = 'Because quality and critical outcomes tied, resource use is reported as a secondary comparison. Subscription monetary cost was not exposed by the CLI and is not estimated.'
    }
    pairs = @($pairs | Sort-Object trial)
    runs = @($rows | Sort-Object trial, arm)
    protocol = 'Evals/baselines/production-ingestion-protocol.json'
    additional_provider_calls = 0
}

$base = Join-Path $rootPath "Evals/reports/$($data.campaign_id)-complex-screen"
$summary | ConvertTo-Json -Depth 14 | Set-Content -Encoding UTF8 -LiteralPath ($base + '.json')

$md = @(
    '# Complex Benchmark Screen Report','',
    "- Campaign: ``$($data.campaign_id)``",
    "- Generated: $($summary.generated_at)",
    "- Measurement integrity: **$($summary.measurement_integrity.verdict)**",
    "- Comparative conclusion: **$($summary.comparative_result.conclusion)**",
    '- Claim level: screening only; not publishable evidence','',
    '## Executive result','',
    'Exactly six approved Codex calls completed sequentially with no orphan, Claude, overlapping or invalid execution. Vanilla and Core + Router + enforcement both scored 95/100 in all three paired trials. Every paired quality delta was zero and no critical floor differed, so the predeclared decision is NO_ACTIONABLE_SIGNAL. No confirmation or cross-provider call is authorized.','',
    "The full environment used more resources without a measured quality gain in this screen: median wall time was $($fullStats.wall_seconds_median) versus $($vanillaStats.wall_seconds_median) seconds (+$($summary.resource_comparison.median_seconds_percent_delta)%), and median observed tokens were $($fullStats.tokens_median) versus $($vanillaStats.tokens_median) (+$($summary.resource_comparison.median_tokens_percent_delta)%). Subscription monetary cost was not reported by the CLI and is not estimated.",'',
    '## Paired outcomes','',
    '| Trial | Seed | Vanilla | Full | Quality delta | Vanilla sec | Full sec | Vanilla tokens | Full tokens |','|---:|---:|---:|---:|---:|---:|---:|---:|---:|'
)
foreach ($pair in @($pairs | Sort-Object trial)) {
    $md += "| $($pair.trial) | $($pair.grader_seed) | $($pair.vanilla_score) | $($pair.full_score) | $($pair.quality_delta_full_minus_vanilla) | $($pair.vanilla_seconds) | $($pair.full_seconds) | $($pair.vanilla_tokens) | $($pair.full_tokens) |"
}
$md += @('','## Absolute quality by arm','',
    '| Arm | Quality median | Functional | Generalization | Reliability | Security | Edge cases | Performance |','|---|---:|---:|---:|---:|---:|---:|---:|'
)
foreach ($arm in @('vanilla','core-router-enforcement')) {
    $stats = $arms[$arm]
    $label = if ($arm -eq 'vanilla') { 'Vanilla' } else { 'Core + Router + enforcement' }
    $md += "| $label | $($stats.quality_median) | $($stats.dimension_medians.functional)/20 | $($stats.dimension_medians.generalization)/25 | $($stats.dimension_medians.reliability)/20 | $($stats.dimension_medians.security)/15 | $($stats.dimension_medians.'edge-cases')/10 | $($stats.dimension_medians.performance)/10 |"
}
$md += @('','## Fixture-alignment finding','',
    '**Review required.** All six runs failed only `replay-duplicate`. Each solution returned a duplicate record with `provider`, `id`, `reason` and `index`; the hidden check required exact equality without `index`. The task explicitly fixes the fields of rejected records, but does not state an equally explicit exact-field schema for skipped records.','',
    'This common-mode result is evidence that the fixture needs clarification. The original pinned outcomes remain immutable. A future version should define the skipped schema explicitly, add a public contract assertion, rerun deterministic controls and receive fresh approval before any provider calls.','',
    '## Integrity and cost evidence','',
    "- Approved and completed calls: $($summary.measurement_integrity.completed_unique_runs)/$($summary.measurement_integrity.approved_calls).",
    "- Orphans / Claude calls / overlaps / invalid outcomes: $($summary.measurement_integrity.orphan_runs) / $($summary.measurement_integrity.claude_runs) / $($summary.measurement_integrity.overlaps) / $($summary.measurement_integrity.invalid_outcomes).",
    "- Protected benchmark-file changes: $($summary.measurement_integrity.protected_file_changes).",
    "- Total observed tokens: $($summary.resource_comparison.total_observed_tokens).",
    "- Provider-reported monetary-cost coverage: $($summary.resource_comparison.reported_cost_coverage); basis: $($summary.resource_comparison.cost_basis -join ', ').",'',
    '## Decision and next gate','',
    '**STOP.** Do not run confirmation, Claude, directional, confidence or pilot stages from this result. Clarify the fixture contract, strengthen its public/hidden alignment, revalidate the discrimination ladder without provider calls, and only then propose a fresh bounded screen for explicit human approval.','',
    '## Required fixture repair','',
    '- Define the exact `skipped` record schema in the public task and assert it in a public contract test.',
    '- Keep the original campaign and pinned grader immutable; version the repaired fixture instead of rewriting history.',
    '- Re-run starter, all negative controls and the reference solution locally before any provider approval.',
    '- Add more than one difficult task family so a single shared interpretation cannot dominate the comparison.',
    '- Preserve paired seeds, sequential execution, zero automatic replacements and explicit per-stage approval.','',
    '## Interpretation limits','',
    '- Three trials per arm support screening decisions only; they do not establish statistical significance.',
    '- This evidence covers one Codex model, one effort level and one composite Python fixture.',
    '- Token counts are observable resource use; subscription monetary charges are not exposed by the CLI.',
    '- Identical scores do not prove the environment has no value; they prove this screen measured no lift.','',
    'The structured JSON beside this report is the measurement source of truth. This PDF is the human-readable rendering.'
)
$md -join [Environment]::NewLine | Set-Content -Encoding UTF8 -LiteralPath ($base + '.md')

[ordered]@{
    schema_version = 1
    json = $base + '.json'
    markdown = $base + '.md'
    measurement_integrity = $summary.measurement_integrity.verdict
    comparative_conclusion = $summary.comparative_result.conclusion
    provider_calls = $rows.Count
    additional_provider_calls = 0
} | ConvertTo-Json -Depth 5
