[CmdletBinding()]
param(
    [string]$DistroName = 'AgenticBench',
    [string]$OutputPath,
    [string]$Root
)

$ErrorActionPreference = 'Stop'
if (-not $Root) { $Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot) }
$rootPath = (Resolve-Path -LiteralPath $Root).Path
if (-not $OutputPath) { $OutputPath = Join-Path $rootPath 'Evals/local/agenticbench-status.json' }
$checks = @()

function Add-Check([string]$Id, [bool]$Passed, [string]$Message) {
    $script:checks += [ordered]@{ id = $Id; status = if ($Passed) { 'PASS' } else { 'FAIL' }; message = $Message }
}

function Invoke-Wsl([string[]]$WslArguments) {
    $old = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $output = & wsl @WslArguments 2>&1 | Out-String
    $exitCode = $LASTEXITCODE
    $ErrorActionPreference = $old
    return [pscustomobject]@{ ExitCode = $exitCode; Output = $output.Trim() }
}

$names = @((& wsl --list --quiet 2>$null) | ForEach-Object { (([string]$_) -replace "`0", '').Trim() } | Where-Object { $_ })
$exists = $DistroName -in $names
Add-Check 'distro-present' $exists $DistroName

if ($exists) {
    $user = Invoke-Wsl @('-d', $DistroName, '--', 'id', '-un')
    Add-Check 'dedicated-user' ($user.ExitCode -eq 0 -and $user.Output -eq 'agenticbench') $user.Output

    $groups = Invoke-Wsl @('-d', $DistroName, '--', 'id', '-nG')
    Add-Check 'unprivileged-groups' ($groups.ExitCode -eq 0 -and $groups.Output -eq 'agenticbench') $groups.Output

    $homeMode = Invoke-Wsl @('-d', $DistroName, '--', 'stat', '-c', '%a', '/home/agenticbench')
    Add-Check 'private-home' ($homeMode.ExitCode -eq 0 -and $homeMode.Output -eq '700') $homeMode.Output

    $mount = Invoke-Wsl @('-d', $DistroName, '-u', 'root', '--', 'mountpoint', '-q', '/mnt/c')
    Add-Check 'windows-drive-not-mounted' ($mount.ExitCode -ne 0) 'C: is not a mount point inside AgenticBench'

    $interop = Invoke-Wsl @('-d', $DistroName, '--', 'printenv', 'WSL_INTEROP')
    Add-Check 'windows-interop-disabled' ($interop.ExitCode -ne 0 -and -not $interop.Output) 'WSL_INTEROP is absent'

    $sudo = Invoke-Wsl @('-d', $DistroName, '--', 'test', '-e', '/usr/bin/sudo')
    Add-Check 'sudo-absent' ($sudo.ExitCode -ne 0) '/usr/bin/sudo is absent'

    $codex = Invoke-Wsl @('-d', $DistroName, '--', '/home/agenticbench/.local/bin/codex', '--version')
    Add-Check 'codex-cli' ($codex.ExitCode -eq 0 -and $codex.Output -match '^codex-cli ') $codex.Output

    $claude = Invoke-Wsl @('-d', $DistroName, '--', '/home/agenticbench/.local/bin/claude', '--version')
    Add-Check 'claude-cli' ($claude.ExitCode -eq 0 -and $claude.Output -match 'Claude Code') $claude.Output

    $runtime = Invoke-Wsl @('-d', $DistroName, '--', 'test', '-x', '/opt/agenticbench/bin/agenticbench-run-provider.sh')
    Add-Check 'root-owned-runtime' ($runtime.ExitCode -eq 0) '/opt/agenticbench/bin'

    $codexAuth = Invoke-Wsl @('-d', $DistroName, '--', '/home/agenticbench/.local/bin/codex', 'login', 'status')
    Add-Check 'codex-auth' ($codexAuth.ExitCode -eq 0) $(if ($codexAuth.ExitCode -eq 0) { 'authenticated' } else { 'login required' })

    $claudeAuth = Invoke-Wsl @('-d', $DistroName, '--', '/home/agenticbench/.local/bin/claude', 'auth', 'status', '--json')
    $claudeLoggedIn = $false
    if ($claudeAuth.ExitCode -eq 0) {
        try { $claudeLoggedIn = [bool](($claudeAuth.Output | ConvertFrom-Json).loggedIn) } catch { $claudeLoggedIn = $false }
    }
    Add-Check 'claude-auth' $claudeLoggedIn $(if ($claudeLoggedIn) { 'authenticated' } else { 'login required' })
}

$failures = @($checks | Where-Object status -eq 'FAIL').Count
$result = [ordered]@{
    schema_version = 1
    generated_at = [datetimeoffset]::Now.ToString('o')
    distro = $DistroName
    ready = ($failures -eq 0)
    failures = $failures
    checks = $checks
}

$parent = Split-Path -Parent $OutputPath
if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
$result | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 -LiteralPath $OutputPath
$result | ConvertTo-Json -Depth 8
if ($failures) { exit 1 }
