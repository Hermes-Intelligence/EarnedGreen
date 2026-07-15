[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Campaign,
    [Parameter(Mandatory = $true)][ValidateSet('calibration', 'complex-screen', 'battery-sentinel', 'battery-diversity', 'smoke', 'directional', 'confidence', 'pilot')][string]$Stage,
    [Parameter(Mandatory = $true)][string]$ApprovedBy,
    [string]$Root
)

$ErrorActionPreference = 'Stop'
if (-not $Root) { $Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot) }
$rootPath = (Resolve-Path -LiteralPath $Root).Path
$path = if ([IO.Path]::IsPathRooted($Campaign)) { (Resolve-Path -LiteralPath $Campaign).Path } else { (Resolve-Path -LiteralPath (Join-Path $rootPath "Evals/experiments/$Campaign")).Path }
$campaignPath = Join-Path $path 'campaign.json'
$data = Get-Content -Raw -Encoding UTF8 -LiteralPath $campaignPath | ConvertFrom-Json
if ($data.status -like 'closed-*') { throw "Campaign is closed with status '$($data.status)'." }
if ([datetimeoffset]$data.provider_snapshot.expires_at -le [datetimeoffset]::Now) { throw 'Campaign provider snapshot expired.' }
$order = if ($Stage -in @('battery-sentinel', 'battery-diversity')) { @('battery-sentinel', 'battery-diversity') } else { @('smoke', 'directional', 'confidence', 'pilot') }
$index = [array]::IndexOf($order, $Stage)
if ($index -gt 0) {
    $previous = @($data.stages | Where-Object id -eq $order[$index - 1])[0]
    if ($previous.status -ne 'complete') { throw "Previous stage '$($previous.id)' is not complete." }
}
if ($Stage -ne 'smoke') {
    $defaults = @($data.provider_snapshot.providers | Where-Object model -eq 'provider-default')
    if ($defaults.Count) { throw 'Every post-smoke stage requires explicit model snapshots; refresh local provider settings and create a new campaign.' }
}
$stageData = @($data.stages | Where-Object id -eq $Stage)[0]
if ($stageData.status -eq 'complete') { throw 'Stage is already complete.' }
if ($stageData.status -eq 'awaiting-replacement-approval') {
    $invalid = @($data.runs | Where-Object { $_.stage -eq $Stage -and $_.status -eq 'invalid_infrastructure' })
    if (-not $invalid.Count) { throw 'Replacement approval requested but no invalid infrastructure runs exist.' }
    foreach ($entry in $invalid) { $entry.status = 'pending'; $entry.run_id = $null }
}

# Fixture admission (pre-spend): approving this stage authorizes provider
# execution, so every fixture scheduled in the stage must hold a fresh
# outcome-harness validity record. Refuse otherwise (fail closed).
$stageFixtures = @($data.runs | Where-Object { $_.stage -eq $Stage } | ForEach-Object { [string]$_.fixture } | Sort-Object -Unique)
if ($stageFixtures.Count) {
    . (Join-Path $PSScriptRoot 'fixture-admission.ps1')
    Assert-FixtureAdmission -RootPath $rootPath -FixtureIds $stageFixtures -Context "approval of stage '$Stage'"
}

$stageData.status = 'approved'
$stageData.approved_at = [datetimeoffset]::Now.ToString('o')
$stageData.approved_by = $ApprovedBy
$data.status = "${Stage}-approved"
$data | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 -LiteralPath $campaignPath
[ordered]@{ campaign_id = $data.campaign_id; stage = $Stage; status = 'approved'; runs = @($data.runs | Where-Object stage -eq $Stage).Count } | ConvertTo-Json
