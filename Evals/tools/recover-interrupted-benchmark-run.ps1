[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Campaign,
    [Parameter(Mandatory = $true)][string]$RunId,
    [Parameter(Mandatory = $true)][string]$Reason,
    [string]$DistroName = 'AgenticBench',
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
$entry = @($data.runs | Where-Object run_id -eq $RunId)[0]
if (-not $entry) { throw 'Run is not linked to this campaign.' }
if ($entry.status -ne 'running') { throw "Only a running entry can be recovered; current status is '$($entry.status)'." }

$processes = & wsl -d $DistroName -u root -- ps -eo args 2>&1 | Out-String
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect AgenticBench processes.' }
if ($processes -match 'agenticbench-run-provider\.sh|codex exec|claude --print') { throw 'Provider is still active; refusing recovery.' }

$validationRaw = & wsl -d $DistroName -u root -- /opt/agenticbench/bin/agenticbench-validate-workspace.sh 2>&1 | Out-String
if ($LASTEXITCODE -ne 0) { throw "Interrupted workspace failed safety validation: $($validationRaw.Trim())" }
$validation = $validationRaw | ConvertFrom-Json

$runPath = (Resolve-Path -LiteralPath (Join-Path $rootPath "Evals/runs/$RunId")).Path
$artifactDir = Join-Path $runPath 'artifacts/infrastructure-invalid'
New-Item -ItemType Directory -Force -Path $artifactDir | Out-Null
$remoteAgentic = "\\wsl.localhost\$DistroName\srv\agenticbench\workspace\.agentic"
foreach ($name in @('provider-events.jsonl', 'provider-stderr.log')) {
    $source = Join-Path $remoteAgentic $name
    if (Test-Path -LiteralPath $source) { Copy-Item -LiteralPath $source -Destination (Join-Path $artifactDir $name) -Force }
}
$eventsPath = Join-Path $artifactDir 'provider-events.jsonl'
$eventsHash = if (Test-Path -LiteralPath $eventsPath) { (Get-FileHash -LiteralPath $eventsPath -Algorithm SHA256).Hash } else { $null }

$attempt = [ordered]@{
    run_id = $RunId
    run_key = $entry.run_key
    provider = $entry.provider
    fixture = $entry.fixture
    arm = $entry.arm
    trial = $entry.trial
    invalidated_at = [datetimeoffset]::Now.ToString('o')
    reason = $Reason
    workspace_files = $validation.files
    workspace_bytes = $validation.bytes
    events_sha256 = $eventsHash
    replacement_required = $true
}
if (-not ($data.PSObject.Properties.Name -contains 'invalid_attempts')) { $data | Add-Member -NotePropertyName invalid_attempts -NotePropertyValue @() }
$data.invalid_attempts = @($data.invalid_attempts) + $attempt
$entry.status = 'invalid_infrastructure'
$stage = @($data.stages | Where-Object id -eq $entry.stage)[0]
$stage.status = 'awaiting-replacement-approval'
$data.status = "awaiting-$($entry.stage)-replacement-approval"
$data | ConvertTo-Json -Depth 14 | Set-Content -Encoding UTF8 -LiteralPath $campaignPath

$manifestPath = Join-Path $runPath 'run-manifest.json'
$manifest = Get-Content -Raw -Encoding UTF8 -LiteralPath $manifestPath | ConvertFrom-Json
$manifest.status = 'infrastructure_invalid'
$manifest | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 -LiteralPath $manifestPath

& wsl -d $DistroName -u root -- /opt/agenticbench/bin/agenticbench-reset-workspace.sh
if ($LASTEXITCODE -ne 0) { throw 'Remote workspace cleanup failed.' }

[ordered]@{
    schema_version = 1
    campaign_id = $data.campaign_id
    invalid_run_id = $RunId
    entry_restored_to = 'invalid_infrastructure'
    events_sha256 = $eventsHash
    remote_workspace_cleaned = $true
    replacement_requires_explicit_approval = $true
} | ConvertTo-Json -Depth 6
