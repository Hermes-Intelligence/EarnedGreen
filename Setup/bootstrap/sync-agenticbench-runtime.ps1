[CmdletBinding()]
param(
    [string]$DistroName = 'AgenticBench',
    [string]$Root
)

$ErrorActionPreference = 'Stop'
if (-not $Root) { $Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot) }
$rootPath = (Resolve-Path -LiteralPath $Root).Path
$source = Join-Path $rootPath 'Setup/bootstrap'
$scripts = @(
    'agenticbench-reset-workspace.sh',
    'agenticbench-run-provider.sh',
    'agenticbench-validate-workspace.sh'
)

& wsl -d $DistroName -- /usr/bin/install -d -m 0700 /home/agenticbench/.agenticbench/stage
if ($LASTEXITCODE -ne 0) { throw 'Cannot create AgenticBench staging directory.' }

$uncRoot = "\\wsl.localhost\$DistroName\home\agenticbench\.agenticbench\stage"
if (-not (Test-Path -LiteralPath $uncRoot)) { $uncRoot = "\\wsl$\$DistroName\home\agenticbench\.agenticbench\stage" }
if (-not (Test-Path -LiteralPath $uncRoot)) { throw 'AgenticBench UNC bridge is unavailable.' }

foreach ($script in $scripts) {
    Copy-Item -LiteralPath (Join-Path $source $script) -Destination (Join-Path $uncRoot $script) -Force
    & wsl -d $DistroName -u root -- /usr/bin/install -m 0755 "/home/agenticbench/.agenticbench/stage/$script" "/opt/agenticbench/bin/$script"
    if ($LASTEXITCODE -ne 0) { throw "Failed to install runtime script: $script" }
}

& wsl -d $DistroName -u root -- /bin/rm -rf -- /home/agenticbench/.agenticbench/stage
if ($LASTEXITCODE -ne 0) { throw 'Failed to remove AgenticBench staging directory.' }

[ordered]@{ schema_version = 1; distro = $DistroName; synced = $true; scripts = $scripts } | ConvertTo-Json -Depth 4

