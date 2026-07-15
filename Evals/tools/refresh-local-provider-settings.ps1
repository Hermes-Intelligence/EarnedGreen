[CmdletBinding()]
param(
    [string]$CodexModel = 'provider-default',
    [string]$ClaudeModel = 'provider-default',
    [ValidateSet('low', 'medium', 'high', 'xhigh')][string]$CodexEffort = 'medium',
    [ValidateSet('low', 'medium', 'high')][string]$ClaudeEffort = 'medium',
    [ValidateRange(1, 30)][int]$TtlDays = 7,
    [string]$DistroName = 'AgenticBench',
    [string]$Root
)

$ErrorActionPreference = 'Stop'
if (-not $Root) { $Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot) }
$rootPath = (Resolve-Path -LiteralPath $Root).Path
foreach ($model in @($CodexModel, $ClaudeModel)) {
    if ($model -notmatch '^[A-Za-z0-9._:-]+$') { throw 'Model selector contains unsafe characters.' }
}

$codexVersion = (& wsl -d $DistroName -- /home/agenticbench/.local/bin/codex --version 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Codex CLI is unavailable in AgenticBench.' }
$claudeVersion = (& wsl -d $DistroName -- /home/agenticbench/.local/bin/claude --version 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Claude CLI is unavailable in AgenticBench.' }

$now = [datetimeoffset]::Now
$settings = [ordered]@{
    schema_version = 1
    generated_at = $now.ToString('o')
    expires_at = $now.AddDays($TtlDays).ToString('o')
    distro = $DistroName
    providers = @(
        [ordered]@{ id = 'codex'; model = $CodexModel; effort = $CodexEffort; cli_version = $codexVersion },
        [ordered]@{ id = 'claude'; model = $ClaudeModel; effort = $ClaudeEffort; cli_version = $claudeVersion }
    )
    note = 'Local ignored snapshot. It contains no credentials and must be refreshed at least weekly.'
}
$path = Join-Path $rootPath 'Evals/local/provider-settings.json'
$settings | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 -LiteralPath $path
$settings | ConvertTo-Json -Depth 8

