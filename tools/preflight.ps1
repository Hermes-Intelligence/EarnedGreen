[CmdletBinding()]
param(
    [ValidateSet("core", "benchmark")][string]$Mode = "core",
    [string]$TargetRepo = (Get-Location).Path,
    [switch]$Json,
    [switch]$NoWrite
)

$ErrorActionPreference = "Stop"
$sourceRoot = Split-Path -Parent $PSScriptRoot
$checks = @()

function Add-Check([string]$Id, [string]$Status, [string]$Message) {
    $script:checks += [pscustomobject]@{ id = $Id; status = $Status; message = $Message }
}

function Invoke-JsonScript([string]$Path, [string[]]$Arguments) {
    $output = & powershell -NoProfile -ExecutionPolicy Bypass -File $Path @Arguments 2>&1 | Out-String
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) { throw "$(Split-Path -Leaf $Path) exited $exitCode`: $($output.Trim())" }
    return ($output | ConvertFrom-Json)
}

$manifestPath = Join-Path $sourceRoot "Runtime/stable/manifest.json"
try {
    $manifest = Get-Content -Raw -Encoding UTF8 -LiteralPath $manifestPath | ConvertFrom-Json
    $required = @($manifest.core, $manifest.router_catalog, $manifest.objective, $manifest.platform_adapters.codex, $manifest.platform_adapters.claude)
    $missing = @($required | Where-Object { -not (Test-Path -LiteralPath (Join-Path $sourceRoot $_)) })
    if ($missing.Count -gt 0) { Add-Check "stable-runtime" "FAIL" "missing manifest targets: $($missing -join ', ')" }
    else { Add-Check "stable-runtime" "PASS" "release=$($manifest.release); all manifest targets present" }
} catch { Add-Check "stable-runtime" "FAIL" $_.Exception.Message }

try {
    $doctor = Invoke-JsonScript (Join-Path $sourceRoot "tools/doctor.ps1") @("-TargetRepo", $TargetRepo, "-Json")
    Add-Check "doctor" $(if ($doctor.passed) { "PASS" } else { "FAIL" }) "failures=$($doctor.failures); warnings=$($doctor.warnings)"
} catch { Add-Check "doctor" "FAIL" $_.Exception.Message }

try {
    $objective = Invoke-JsonScript (Join-Path $sourceRoot "tools/objective-check.ps1") @("-ObjectivePath", (Join-Path $sourceRoot $manifest.objective), "-AllowIncomplete", "-Json")
    # objective-check exits 2 (-> Invoke-JsonScript throws -> FAIL below) on structural
    # errors even with -AllowIncomplete. A clean-but-incomplete objective returns exit 0
    # with complete=false; report that as WARN, not a hardcoded PASS.
    $structuralErrors = @($objective.errors).Count
    $status = if ($structuralErrors -gt 0) { "FAIL" } elseif (-not $objective.complete) { "WARN" } else { "PASS" }
    Add-Check "objective-integrity" $status "requirements=$($objective.requirements); complete=$($objective.complete); structural_errors=$structuralErrors"
} catch { Add-Check "objective-integrity" "FAIL" $_.Exception.Message }

$handoffPath = Join-Path $sourceRoot "workstreams/current.json"
try {
    $handoff = Invoke-JsonScript (Join-Path $sourceRoot "tools/handoff-check.ps1") @("-HandoffPath", $handoffPath)
    Add-Check "current-workstream" "PASS" "age_hours=$($handoff.age_hours); next=$($handoff.next_action)"
} catch { Add-Check "current-workstream" "FAIL" $_.Exception.Message }

$setupRequired = $false
$setupPath = Join-Path $sourceRoot "Evals/local/setup-status.json"
if (-not (Test-Path -LiteralPath $setupPath)) {
    $setupRequired = $true
    Add-Check "local-setup" "WARN" "No machine-local setup record. On a fresh clone run setup.ps1 -InstallCodex -GlobalPointers."
} else {
    try {
        $setup = Get-Content -Raw -Encoding UTF8 -LiteralPath $setupPath | ConvertFrom-Json
        $sameRoot = [string]::Equals([string]$setup.root, [string]$sourceRoot, [System.StringComparison]::OrdinalIgnoreCase)
        if (-not $sameRoot -or -not $setup.core_ready) {
            $setupRequired = $true
            Add-Check "local-setup" "FAIL" "Setup record is for another root or core_ready=false; rerun setup.ps1."
        } else {
            Add-Check "local-setup" "PASS" "persistent setup found; reboot does not require reinstall or login"
        }
    } catch {
        $setupRequired = $true
        Add-Check "local-setup" "FAIL" $_.Exception.Message
    }
}

if ($Mode -eq "benchmark") {
    $providerPath = Join-Path $sourceRoot "Evals/local/provider-settings.json"
    try {
        $provider = Get-Content -Raw -Encoding UTF8 -LiteralPath $providerPath | ConvertFrom-Json
        if ([datetimeoffset]$provider.expires_at -le [datetimeoffset]::Now) { throw "local provider snapshot expired" }
        $ids = @($provider.providers.id | Sort-Object -Unique)
        if ('codex' -notin $ids -or 'claude' -notin $ids) { throw "local provider snapshot must contain Codex and Claude" }
        Add-Check "provider-record" "PASS" "providers=$($ids -join ','); expires=$($provider.expires_at); distro=$($provider.distro)"
    } catch { Add-Check "provider-record" "FAIL" $_.Exception.Message }

    try {
        $statusPath = Join-Path $sourceRoot "Evals/local/agenticbench-status.json"
        $oldPreference = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        $doctorOutput = & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $sourceRoot "Setup/bootstrap/doctor-agenticbench.ps1") -Root $sourceRoot -OutputPath $statusPath 2>&1 | Out-String
        $doctorExit = $LASTEXITCODE
        $ErrorActionPreference = $oldPreference
        $proof = Get-Content -Raw -Encoding UTF8 -LiteralPath $statusPath | ConvertFrom-Json
        if ($doctorExit -ne 0 -or -not $proof.ready) { throw "AgenticBench doctor failed with $($proof.failures) checks" }
        Add-Check "provider-live-login" "PASS" "Codex and Claude logins are currently valid"
        Add-Check "wsl-isolation-live" "PASS" "dedicated-wsl-no-windows-mount"
    } catch {
        Add-Check "provider-live-login" "FAIL" $_.Exception.Message
        Add-Check "wsl-isolation-live" "FAIL" $_.Exception.Message
    }
}

$failures = @($checks | Where-Object { $_.status -eq "FAIL" }).Count
$warnings = @($checks | Where-Object { $_.status -eq "WARN" }).Count
$nextAction = if ($setupRequired) {
    "From the repository root run: powershell -ExecutionPolicy Bypass -File setup.ps1 -InstallCodex -GlobalPointers"
} elseif ($failures -gt 0) {
    "Resolve the failed preflight check before substantive work. Do not reinstall components that already pass."
} else {
    [string]$handoff.next_action
}
$result = [ordered]@{
    schema_version = 1
    generated_at = [datetimeoffset]::Now.ToString("o")
    source_root = $sourceRoot
    target_repo = $TargetRepo
    mode = $Mode
    passed = ($failures -eq 0)
    setup_required = $setupRequired
    failures = $failures
    warnings = $warnings
    checks = $checks
    current_workstream = $handoffPath
    next_action = $nextAction
}

if (-not $NoWrite) {
    $localDir = Join-Path $sourceRoot "Evals/local"
    if (-not (Test-Path -LiteralPath $localDir)) { New-Item -ItemType Directory -Force -Path $localDir | Out-Null }
    $result | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $localDir "preflight-status.json")
}

if ($Json) { $result | ConvertTo-Json -Depth 8 }
else {
    foreach ($check in $checks) { Write-Host ("[{0}] {1}: {2}" -f $check.status, $check.id, $check.message) }
    Write-Host "Preflight: mode=$Mode failures=$failures warnings=$warnings"
    Write-Host "Next: $nextAction"
}
if ($failures -gt 0) { exit 2 }
exit 0
