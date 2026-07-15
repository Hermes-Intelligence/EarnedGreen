# Static platform-portability lint for HOST-side eval artifacts (REQ-WIN-001).
#
# Host-side PowerShell and fixture-contract JSON must never depend on POSIX-only
# launchers: the MS-Store 'python3' alias exits 9009 on Windows, and 'jq', 'npx'
# and 'bash -c' are not guaranteed on the host. WSL-scoped files (Evals/isolation/*.sh,
# Setup/bootstrap/*.sh and command strings that are built for wsl.exe) are exempt:
# occurrences inside recognizable WSL-invocation context are recorded as
# wsl-context notes instead of failures.
[CmdletBinding()]
param(
    [string]$Root,
    [string]$OutputPath
)

$ErrorActionPreference = 'Stop'
if (-not $Root) { $Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot) }
$rootPath = (Resolve-Path -LiteralPath $Root).Path

# Build the banned literals by concatenation so this file never matches itself
# and so injected copies of this scanner cannot be hidden by self-exemption text.
$py3 = 'python' + '3'
$patterns = @(
    [pscustomobject]@{ id = 'python3-host-alias'; regex = ('(?<![\w-])' + $py3 + '\b') },
    [pscustomobject]@{ id = 'env-python3-shebang'; regex = ('/usr/bin/env\s+' + $py3) },
    [pscustomobject]@{ id = 'jq-host-dependency'; regex = '(?<![\w.\-])jq\s' },
    [pscustomobject]@{ id = 'npx-host-dependency'; regex = '(?<![\w.\-])npx\s' },
    [pscustomobject]@{ id = 'bash-dash-c-host-shell'; regex = '(?<![\w.\-])bash\s+-c\b' }
)

function Get-RelativePath([string]$FullName) {
    $relative = $FullName
    if ($relative.StartsWith($rootPath, [StringComparison]::OrdinalIgnoreCase)) {
        $relative = $relative.Substring($rootPath.Length)
    }
    return $relative.TrimStart('\', '/').Replace('\', '/')
}

function Test-ExemptPath([string]$RelativePath) {
    if ($RelativePath -like 'Evals/isolation/*') { return $true }
    if ($RelativePath -like 'Setup/bootstrap/*') { return $true }
    if ($RelativePath -like '*.sh') { return $true }
    return $false
}

$targets = @()
$powershellDirs = @(
    (Join-Path $rootPath 'Evals'),
    (Join-Path $rootPath 'Evals/tools'),
    (Join-Path $rootPath 'Evals/adapters/providers')
)
foreach ($dir in $powershellDirs) {
    if (Test-Path -LiteralPath $dir) {
        $targets += @(Get-ChildItem -LiteralPath $dir -Filter '*.ps1' -File)
    }
}
$jsonCandidates = @((Join-Path $rootPath 'Evals/fixtures/catalog.json'))
foreach ($dir in @((Join-Path $rootPath 'Evals/baselines'), (Join-Path $rootPath 'Evals/adapters/providers'))) {
    if (Test-Path -LiteralPath $dir) {
        $jsonCandidates += @(Get-ChildItem -LiteralPath $dir -Filter '*.json' -File | ForEach-Object { $_.FullName })
    }
}
foreach ($candidate in @($jsonCandidates | Sort-Object -Unique)) {
    if (Test-Path -LiteralPath $candidate) { $targets += @(Get-Item -LiteralPath $candidate) }
}
$selfPath = $PSCommandPath
$targets = @($targets | Where-Object { $_.FullName -ne $selfPath } | Sort-Object FullName -Unique)

$findings = @()
$notes = @()
$scanned = 0
foreach ($file in $targets) {
    $relative = Get-RelativePath $file.FullName
    if (Test-ExemptPath $relative) { continue }
    $scanned++
    $isPowerShell = ($file.Extension -eq '.ps1')
    $fileNameIsWsl = ($file.Name -match '(?i)wsl')
    $lines = @(Get-Content -Encoding UTF8 -LiteralPath $file.FullName)
    for ($index = 0; $index -lt $lines.Count; $index++) {
        $line = [string]$lines[$index]
        if ($isPowerShell -and $line -match '^\s*#') { continue }
        foreach ($pattern in $patterns) {
            if ($line -notmatch $pattern.regex) { continue }
            $entry = [ordered]@{
                file = $relative
                line = $index + 1
                pattern = $pattern.id
                text = $line.Trim()
            }
            # Mixed-file exemption: a hit on a line that is recognizably part of
            # a WSL command construction (or inside a *wsl* adapter) is allowed
            # with a wsl-context note rather than reported as a host defect.
            if ($fileNameIsWsl -or $line -match '(?i)wsl') {
                $entry.context = 'wsl-context'
                $notes += [pscustomobject]$entry
            } else {
                $findings += [pscustomobject]$entry
            }
        }
    }
}

$failedFiles = @($findings | ForEach-Object { $_.file } | Sort-Object -Unique)
$report = [ordered]@{
    schema_version = 1
    run_at = [datetimeoffset]::Now.ToString('o')
    root = $rootPath
    patterns = @($patterns | ForEach-Object { $_.id })
    cases = $scanned
    passed = $scanned - $failedFiles.Count
    failed = $failedFiles.Count
    findings = $findings
    wsl_context_notes = $notes
}
if (-not $OutputPath) {
    $reportsDir = Join-Path $rootPath 'Evals/reports'
    if (Test-Path -LiteralPath $reportsDir) {
        $OutputPath = Join-Path $reportsDir ("{0}-platform-portability.json" -f (Get-Date -Format 'yyyy-MM-dd-HHmmss'))
    }
}
if ($OutputPath) { $report | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 -LiteralPath $OutputPath }
$report | ConvertTo-Json -Depth 8
if ($findings.Count) { exit 1 }
