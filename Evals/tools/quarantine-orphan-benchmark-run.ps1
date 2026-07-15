[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Campaign,
    [Parameter(Mandatory = $true)][string]$RunId,
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
if (@($data.runs | Where-Object run_id -eq $RunId).Count) { throw 'Run is linked to the campaign; use the overlapping-run invalidator.' }
if (@($data.invalid_attempts | Where-Object run_id -eq $RunId).Count) { throw 'Run is already quarantined.' }

$executionPath = Join-Path $rootPath "Evals/runs/$RunId/provider-execution.json"
$manifestPath = Join-Path $rootPath "Evals/runs/$RunId/run-manifest.json"
$execution = Get-Content -Raw -Encoding UTF8 -LiteralPath $executionPath | ConvertFrom-Json
$manifest = Get-Content -Raw -Encoding UTF8 -LiteralPath $manifestPath | ConvertFrom-Json
$overlaps = @()
foreach ($known in @($data.invalid_attempts)) {
    $knownPath = Join-Path $rootPath "Evals/runs/$($known.run_id)/provider-execution.json"
    if (-not (Test-Path -LiteralPath $knownPath)) { continue }
    $other = Get-Content -Raw -Encoding UTF8 -LiteralPath $knownPath | ConvertFrom-Json
    $latestStart = @([datetimeoffset]$execution.started_at, [datetimeoffset]$other.started_at | Sort-Object -Descending)[0]
    $earliestFinish = @([datetimeoffset]$execution.finished_at, [datetimeoffset]$other.finished_at | Sort-Object)[0]
    if ($latestStart -lt $earliestFinish) { $overlaps += $known.run_id }
}
if (-not $overlaps.Count) { throw 'Orphan run does not overlap a recorded invalid infrastructure attempt.' }

if (-not ($execution.PSObject.Properties.Name -contains 'validity')) { $execution | Add-Member validity 'invalid_infrastructure' } else { $execution.validity = 'invalid_infrastructure' }
if (-not ($execution.PSObject.Properties.Name -contains 'invalidation_reason')) { $execution | Add-Member invalidation_reason $Reason } else { $execution.invalidation_reason = $Reason }
$execution | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 -LiteralPath $executionPath
$manifest.status = 'infrastructure_invalid_orphan_concurrency'
$manifest | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 -LiteralPath $manifestPath
if (-not ($data.PSObject.Properties.Name -contains 'invalid_attempts')) { $data | Add-Member invalid_attempts @() }
$data.invalid_attempts = @($data.invalid_attempts) + [ordered]@{run_id=$RunId;run_key=$null;provider=($manifest.provider -replace '-agenticbench$','');fixture=$manifest.fixture;arm=$manifest.arm;trial=$manifest.trial;invalidated_at=[datetimeoffset]::Now.ToString('o');reason=$Reason;overlaps=@($overlaps);replacement_required=$false;orphaned_by_campaign_write_race=$true}
$data | ConvertTo-Json -Depth 14 | Set-Content -Encoding UTF8 -LiteralPath $campaignPath
[ordered]@{schema_version=1;campaign_id=$data.campaign_id;quarantined_run_id=$RunId;overlaps=@($overlaps);replacement_required=$false;status=$data.status}|ConvertTo-Json -Depth 6
