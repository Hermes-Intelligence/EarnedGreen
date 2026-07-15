[CmdletBinding()]
param(
    [switch]$Create,
    [switch]$UpdateTools,
    [switch]$RefreshProviderCatalog,
    [switch]$LoginCodex,
    [switch]$LoginClaude,
    [switch]$SkipDoctor,
    [string]$DistroName = 'AgenticBench'
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$bootstrap = Join-Path $root 'Setup/bootstrap'

function Get-DistroNames {
    return @((& wsl --list --quiet 2>$null) | ForEach-Object { (([string]$_) -replace "`0", '').Trim() } | Where-Object { $_ })
}

function Convert-ToWslPath([string]$Path) {
    $full = [IO.Path]::GetFullPath($Path)
    if ($full -notmatch '^([A-Za-z]):\\(.*)$') { throw "Unsupported Windows path: $full" }
    return "/mnt/$($Matches[1].ToLowerInvariant())/$($Matches[2].Replace('\','/'))"
}

$names = Get-DistroNames
if ($DistroName -notin $names) {
    if (-not $Create) { throw "Missing $DistroName. Run this script with -Create once." }
    if ('Debian' -in $names) { throw 'A Debian distro already exists. The setup refuses to reuse or delete it; install AgenticBench from a separate fresh rootfs.' }

    & wsl --install -d Debian --no-launch
    if ($LASTEXITCODE -ne 0) { throw 'Debian package installation failed.' }
    $names = Get-DistroNames
    if ('Debian' -notin $names) {
        $package = Get-AppxPackage TheDebianProject.DebianGNULinux -ErrorAction Stop
        $launcher = Join-Path $package.InstallLocation 'debian.exe'
        & $launcher install --root
        if ($LASTEXITCODE -ne 0) { throw 'Fresh Debian registration failed.' }
    }

    & wsl -d Debian -u root -- sh -c 'test -z "$(find /home -mindepth 1 -maxdepth 1 -print -quit)"'
    if ($LASTEXITCODE -ne 0) { throw 'Fresh Debian validation failed; refusing to copy it.' }

    $archive = Join-Path $env:TEMP ("agenticbench-{0}.tar" -f [guid]::NewGuid().ToString('N'))
    $install = Join-Path $env:LOCALAPPDATA 'AgenticBenchWSL'
    if (Test-Path -LiteralPath $install) { throw "Refusing to overwrite existing path: $install" }
    & wsl --terminate Debian
    & wsl --export Debian $archive
    if ($LASTEXITCODE -ne 0) { throw 'Fresh rootfs export failed.' }
    New-Item -ItemType Directory -Path $install | Out-Null
    & wsl --import $DistroName $install $archive --version 2
    if ($LASTEXITCODE -ne 0) { throw 'AgenticBench import failed.' }

    $provision = Convert-ToWslPath (Join-Path $bootstrap 'provision-agenticbench.sh')
    $tools = Convert-ToWslPath (Join-Path $bootstrap 'install-agenticbench-tools.sh')
    & wsl -d $DistroName -u root -- bash $provision
    if ($LASTEXITCODE -ne 0) { throw 'AgenticBench base provisioning failed.' }
    & wsl -d $DistroName -u agenticbench -- bash $tools
    if ($LASTEXITCODE -ne 0) { throw 'Provider CLI installation failed.' }
    & wsl --terminate $DistroName

    & wsl --unregister Debian
    if ($LASTEXITCODE -ne 0) { throw 'Temporary Debian cleanup failed.' }
    $resolvedArchive = [IO.Path]::GetFullPath($archive)
    $tempRoot = [IO.Path]::GetFullPath($env:TEMP).TrimEnd('\') + '\'
    if (-not $resolvedArchive.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe temporary archive path.' }
    Remove-Item -LiteralPath $resolvedArchive -Force
}

& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $bootstrap 'sync-agenticbench-runtime.ps1') -DistroName $DistroName -Root $root | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'AgenticBench runtime sync failed.' }

if ($UpdateTools -and -not $Create) {
    $stage = '/home/agenticbench/.agenticbench/install-agenticbench-tools.sh'
    $unc = "\\wsl.localhost\$DistroName\home\agenticbench\.agenticbench\install-agenticbench-tools.sh"
    Copy-Item -LiteralPath (Join-Path $bootstrap 'install-agenticbench-tools.sh') -Destination $unc -Force
    & wsl -d $DistroName -- bash $stage
    if ($LASTEXITCODE -ne 0) { throw 'Provider CLI update failed.' }
    & wsl -d $DistroName -- rm -f -- $stage
}

$codex = '/home/agenticbench/.local/bin/codex'
$claude = '/home/agenticbench/.local/bin/claude'
if ($LoginCodex) {
    & wsl -d $DistroName -- $codex login --device-auth
    if ($LASTEXITCODE -ne 0) { throw 'Codex login failed.' }
}
if ($LoginClaude) {
    & wsl -d $DistroName -- $claude auth login
    if ($LASTEXITCODE -ne 0) { throw 'Claude login failed.' }
}

$providerSettings = Join-Path $root 'Evals/local/provider-settings.json'
if ($Create -or $RefreshProviderCatalog -or -not (Test-Path -LiteralPath $providerSettings)) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'Evals/tools/refresh-local-provider-settings.ps1') -Root $root | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Local provider snapshot refresh failed.' }
}

if (-not $SkipDoctor) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $bootstrap 'doctor-agenticbench.ps1') -DistroName $DistroName -Root $root
    exit $LASTEXITCODE
}
