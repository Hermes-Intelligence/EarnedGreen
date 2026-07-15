[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Campaign,
    [Parameter(Mandatory = $true)][ValidateCount(2, 2)][string[]]$RunIds,
    [Parameter(Mandatory = $true)][string]$Reason,
    [string]$Root
)

$ErrorActionPreference = 'Stop'
if (-not $Root) { $Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot) }
$rootPath = (Resolve-Path -LiteralPath $Root).Path
$experimentsRoot = (Resolve-Path -LiteralPath (Join-Path $rootPath 'Evals/experiments')).Path
$campaignDir = if ([IO.Path]::IsPathRooted($Campaign)) { (Resolve-Path -LiteralPath $Campaign).Path } else { (Resolve-Path -LiteralPath (Join-Path $experimentsRoot $Campaign)).Path }
if (-not $campaignDir.StartsWith($experimentsRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Campaign escaped Evals/experiments.' }
$campaignPath = Join-Path $campaignDir 'campaign.json'
$data = Get-Content -Raw -Encoding UTF8 -LiteralPath $campaignPath | ConvertFrom-Json

$items = @()
foreach ($runId in $RunIds) {
    $entry = @($data.runs | Where-Object run_id -eq $runId)[0]
    if (-not $entry) { throw "Run is not linked to campaign: $runId" }
    $executionPath = Join-Path $rootPath "Evals/runs/$runId/provider-execution.json"
    if (-not (Test-Path -LiteralPath $executionPath)) { throw "Provider execution metadata missing: $runId" }
    $execution = Get-Content -Raw -Encoding UTF8 -LiteralPath $executionPath | ConvertFrom-Json
    $items += [pscustomobject]@{ entry = $entry; execution = $execution; run_id = $runId; path = $executionPath }
}

$latestStart = @($items | ForEach-Object { [datetimeoffset]$_.execution.started_at } | Sort-Object -Descending)[0]
$earliestFinish = @($items | ForEach-Object { [datetimeoffset]$_.execution.finished_at } | Sort-Object)[0]
if ($latestStart -ge $earliestFinish) { throw 'The supplied provider intervals do not overlap.' }
$overlapSeconds = [math]::Round(($earliestFinish - $latestStart).TotalSeconds, 3)

if (-not ($data.PSObject.Properties.Name -contains 'invalid_attempts')) { $data | Add-Member -NotePropertyName invalid_attempts -NotePropertyValue @() }
$limit = if ($data.loop.PSObject.Properties.Name -contains 'max_infrastructure_replacements') { [int]$data.loop.max_infrastructure_replacements } else { 2 }
if (@($data.invalid_attempts).Count + $items.Count -gt $limit) { throw 'Infrastructure replacement ceiling would be exceeded.' }

# Validate stage consistency BEFORE mutating anything on disk. Previously this
# check ran after the mutation loop below, so a mixed-stage request had already
# rewritten both runs' execution + manifest files and the campaign's
# invalid_attempts before throwing, leaving inconsistent state behind.
$stageId = $items[0].entry.stage
if (@($items | Where-Object { $_.entry.stage -ne $stageId }).Count) { throw 'Runs belong to different stages.' }

foreach ($item in $items) {
    $item.entry.status = 'invalid_infrastructure'
    $attempt = [ordered]@{
        run_id = $item.run_id
        run_key = $item.entry.run_key
        provider = $item.entry.provider
        fixture = $item.entry.fixture
        arm = $item.entry.arm
        trial = $item.entry.trial
        invalidated_at = [datetimeoffset]::Now.ToString('o')
        reason = $Reason
        overlap_seconds = $overlapSeconds
        replacement_required = $true
    }
    $data.invalid_attempts = @($data.invalid_attempts) + $attempt

    $execution = $item.execution
    if (-not ($execution.PSObject.Properties.Name -contains 'validity')) { $execution | Add-Member -NotePropertyName validity -NotePropertyValue 'invalid_infrastructure' } else { $execution.validity = 'invalid_infrastructure' }
    if (-not ($execution.PSObject.Properties.Name -contains 'invalidation_reason')) { $execution | Add-Member -NotePropertyName invalidation_reason -NotePropertyValue $Reason } else { $execution.invalidation_reason = $Reason }
    $execution | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 -LiteralPath $item.path

    $manifestPath = Join-Path $rootPath "Evals/runs/$($item.run_id)/run-manifest.json"
    $manifest = Get-Content -Raw -Encoding UTF8 -LiteralPath $manifestPath | ConvertFrom-Json
    $manifest.status = 'infrastructure_invalid_concurrency'
    $manifest | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 -LiteralPath $manifestPath
}

$stage = @($data.stages | Where-Object id -eq $stageId)[0]
$stage.status = 'awaiting-replacement-approval'
$data.status = "awaiting-$stageId-replacement-approval"
$data | ConvertTo-Json -Depth 14 | Set-Content -Encoding UTF8 -LiteralPath $campaignPath

[ordered]@{
    schema_version = 1
    campaign_id = $data.campaign_id
    stage = $stageId
    invalidated_run_ids = $RunIds
    overlap_seconds = $overlapSeconds
    status = $data.status
    replacement_runs_required = $items.Count
} | ConvertTo-Json -Depth 6
