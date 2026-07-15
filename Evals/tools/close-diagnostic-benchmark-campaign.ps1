[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Campaign,
    [Parameter(Mandatory = $true)][string[]]$Findings,
    [Parameter(Mandatory = $true)][string]$ClosedBy,
    [string]$Root
)
$ErrorActionPreference = 'Stop'
if (-not $Root) { $Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot) }
$rootPath = (Resolve-Path -LiteralPath $Root).Path
$experimentsRoot = (Resolve-Path -LiteralPath (Join-Path $rootPath 'Evals/experiments')).Path
$campaignDir = if ([IO.Path]::IsPathRooted($Campaign)) { (Resolve-Path -LiteralPath $Campaign).Path } else { (Resolve-Path -LiteralPath (Join-Path $experimentsRoot $Campaign)).Path }
if (-not $campaignDir.StartsWith($experimentsRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Campaign escaped Evals/experiments.' }
$path = Join-Path $campaignDir 'campaign.json'
$data = Get-Content -Raw -Encoding UTF8 -LiteralPath $path | ConvertFrom-Json
if ($data.status -eq 'closed-diagnostic-invalid') { throw 'Campaign is already closed.' }
if (-not @($data.invalid_attempts).Count) { throw 'Refusing diagnostic closure without preserved invalid-attempt evidence.' }
$data.status = 'closed-diagnostic-invalid'
if (-not ($data.PSObject.Properties.Name -contains 'publishable')) { $data | Add-Member publishable $false } else { $data.publishable = $false }
if (-not ($data.PSObject.Properties.Name -contains 'diagnostic_closure')) { $data | Add-Member diagnostic_closure $null }
$data.diagnostic_closure = [ordered]@{closed_at=[datetimeoffset]::Now.ToString('o');closed_by=$ClosedBy;findings=@($Findings);disposition='Retain raw evidence; exclude campaign from comparative scoring; require a new campaign and fresh human approval after deterministic harness fixes.'}
foreach ($stage in @($data.stages | Where-Object { $_.status -in @('approved','running','awaiting-replacement-approval') })) { $stage.status = 'diagnostic-invalid' }
$data | ConvertTo-Json -Depth 14 | Set-Content -Encoding UTF8 -LiteralPath $path
[ordered]@{schema_version=1;campaign_id=$data.campaign_id;status=$data.status;publishable=$data.publishable;invalid_attempts=@($data.invalid_attempts).Count;additional_provider_calls=0}|ConvertTo-Json -Depth 6
