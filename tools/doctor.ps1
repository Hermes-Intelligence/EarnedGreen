[CmdletBinding()]
param(
    [string]$TargetRepo = (Get-Location).Path,
    [switch]$Json
)

$ErrorActionPreference = "Stop"
$sourceRoot = Split-Path -Parent $PSScriptRoot
$checks = @()

function Add-Check([string]$id, [string]$status, [string]$message) {
    $script:checks += [pscustomobject]@{ id=$id; status=$status; message=$message }
}

foreach ($path in @("Runtime/stable/manifest.json", "Core/runtime.md", "Router/catalog/modules.json", "Objectives/active/OBJ-20260712-agentic-work-best-practices.json")) {
    $full = Join-Path $sourceRoot $path
    Add-Check "file:$path" $(if (Test-Path -LiteralPath $full) { "PASS" } else { "FAIL" }) $full
}

try {
    $manifest = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $sourceRoot "Runtime/stable/manifest.json") | ConvertFrom-Json
    Add-Check "stable-manifest" "PASS" "release=$($manifest.release), status=$($manifest.status)"
} catch { Add-Check "stable-manifest" "FAIL" $_.Exception.Message }

$globalPointers = @(
    @{ id="global-claude"; path=Join-Path $HOME ".claude/CLAUDE.md" },
    @{ id="global-codex"; path=Join-Path $HOME ".codex/AGENTS.md" }
)
foreach ($p in $globalPointers) {
    if (-not (Test-Path -LiteralPath $p.path)) { Add-Check $p.id "FAIL" "missing: $($p.path)"; continue }
    $body = Get-Content -Raw -Encoding UTF8 -LiteralPath $p.path
    Add-Check $p.id $(if ($body.Contains($sourceRoot)) { "PASS" } else { "WARN" }) $(if ($body.Contains($sourceRoot)) { "points to source root" } else { "does not mention current source root" })
}

foreach ($command in @("git", "pwsh", "powershell", "node", "python", "python3", "jq", "npx")) {
    $found = Get-Command $command -ErrorAction SilentlyContinue
    Add-Check "command:$command" $(if ($found) { "PASS" } else { "INFO" }) $(if ($found) { $found.Source } else { "not found" })
}

if ($sourceRoot -match "OneDrive") { Add-Check "onedrive" "WARN" "Source root is under OneDrive; test file locks, sync conflicts, long paths and concurrent writers." }
if ($IsWindows -or $env:OS -eq "Windows_NT") {
    Add-Check "platform" "PASS" "Windows/PowerShell detected; Unix-only hooks require an explicit compatible runtime."
    $policy = Get-ExecutionPolicy
    Add-Check "powershell-execution-policy" $(if ($policy -eq "Restricted") { "WARN" } else { "PASS" }) "policy=$policy; use signed scripts or an explicitly scoped process-level bypass for trusted repo tooling"
    $longPaths = (Get-ItemProperty -LiteralPath 'HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem' -Name LongPathsEnabled -ErrorAction SilentlyContinue).LongPathsEnabled
    Add-Check "windows-long-paths" $(if ($longPaths -eq 1) { "PASS" } else { "WARN" }) "LongPathsEnabled=$longPaths; keep benchmark workspaces shallow or enable the Windows long-path policy"
}

try {
    $reviewed = (Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $sourceRoot "Research/sources/registry.json") | ConvertFrom-Json).sources
    $migrated = (Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $sourceRoot "Research/sources/claude-v1-migration.json") | ConvertFrom-Json).sources
    $urls = @($reviewed.url) + @($migrated.url)
    Add-Check "source-memory" $(if (@($migrated).Count -eq 47 -and @($urls | Sort-Object -Unique).Count -eq $urls.Count) { "PASS" } else { "FAIL" }) "reviewed=$(@($reviewed).Count) migrated=$(@($migrated).Count) composite_unique=$(@($urls | Sort-Object -Unique).Count)"
} catch { Add-Check "source-memory" "FAIL" $_.Exception.Message }

try {
    $providers = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $sourceRoot "Models/providers.json") | ConvertFrom-Json
    $profiles = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $sourceRoot "Models/profiles.json") | ConvertFrom-Json
    $expired = [datetimeoffset]::Now -gt ([datetimeoffset]$providers.expires_at)
    Add-Check "model-catalog" $(if ($expired) { "WARN" } else { "PASS" }) "profiles=$(@($profiles.profiles).Count) providers=$(@($providers.providers).Count) expires=$($providers.expires_at) recommendation_only=$($providers.policy.recommendation_only)"
} catch { Add-Check "model-catalog" "FAIL" $_.Exception.Message }

$target = Resolve-Path -LiteralPath $TargetRepo -ErrorAction SilentlyContinue
if (-not $target) { Add-Check "target-repo" "FAIL" "Target repository does not exist: $TargetRepo" }
else {
    $hasAgent = Test-Path -LiteralPath (Join-Path $target.Path "AGENTS.md")
    $hasClaude = Test-Path -LiteralPath (Join-Path $target.Path "CLAUDE.md")
    Add-Check "target-pointers" $(if ($hasAgent -and $hasClaude) { "PASS" } else { "WARN" }) "AGENTS=$hasAgent CLAUDE=$hasClaude"
}

$contractChars = (Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $sourceRoot "Claude/OPERATING_CONTRACT.md")).Length + (Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $sourceRoot "Codex/OPERATING_CONTRACT.md")).Length
Add-Check "legacy-contract-size" $(if ($contractChars -gt 30000) { "WARN" } else { "PASS" }) "$contractChars characters; long contracts are reference-only until routed"

$fail = @($checks | Where-Object { $_.status -eq "FAIL" }).Count
$warn = @($checks | Where-Object { $_.status -eq "WARN" }).Count
$result = [ordered]@{ source_root=$sourceRoot; target_repo=$TargetRepo; passed=($fail -eq 0); failures=$fail; warnings=$warn; checks=$checks }
if ($Json) { $result | ConvertTo-Json -Depth 6 }
else {
    foreach ($c in $checks) { Write-Host ("[{0}] {1}: {2}" -f $c.status, $c.id, $c.message) }
    Write-Host "Doctor result: failures=$fail warnings=$warn"
}
if ($fail -gt 0) { exit 2 }
exit 0
