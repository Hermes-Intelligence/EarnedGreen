[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Candidate,
    [switch]$Approve,
    [string]$ApprovedBy,
    [string]$Root,
    [switch]$SkipReleaseGate,
    [string]$SkipReleaseGateReason
)
$ErrorActionPreference = "Stop"
if (-not $Root) { $Root = Split-Path -Parent $PSScriptRoot }

# Portable structural validation of the promotion manifest. Test-Json is not
# available on Windows PowerShell 5.1, so enforce the schema's load-bearing
# constraints directly. A candidate cannot weaken its own gate by omitting evals
# or declaring a zero-pass threshold.
function Assert-PromotionManifest($m) {
    foreach ($key in @("schema_version","candidate_id","release","status","stable_manifest_before_sha256","required_evals","files")) {
        if ($null -eq $m.$key) { throw "Promotion manifest missing required field: $key" }
    }
    if ([int]$m.schema_version -ne 1) { throw "Promotion manifest schema_version must be 1." }
    if ($m.status -notin @("awaiting-eval","awaiting-approval")) { throw "Promotion manifest status must be awaiting-eval or awaiting-approval." }
    if ($m.stable_manifest_before_sha256 -notmatch '^[A-Fa-f0-9]{64}$') { throw "stable_manifest_before_sha256 must be a 64-hex SHA-256." }
    $evals = @($m.required_evals)
    if ($evals.Count -lt 1) { throw "Promotion requires at least one required_evals entry; a candidate cannot self-declare an empty eval set." }
    foreach ($e in $evals) {
        if ([string]::IsNullOrWhiteSpace([string]$e.report)) { throw "Each required_evals entry needs a report path." }
        if ($null -eq $e.minimum_passed -or [int]$e.minimum_passed -lt 1) { throw "required_evals.minimum_passed must be >= 1 (report $($e.report))." }
        if ($null -eq $e.maximum_failed -or [int]$e.maximum_failed -lt 0) { throw "required_evals.maximum_failed must be >= 0 (report $($e.report))." }
    }
    if (@($m.files).Count -lt 1) { throw "Promotion manifest must list at least one file." }
}
$rootPath = (Resolve-Path -LiteralPath $Root).Path
$candidateRoot = Join-Path $rootPath "Research/candidate-packages"
$candidatePath = if ([IO.Path]::IsPathRooted($Candidate)) { (Resolve-Path -LiteralPath $Candidate).Path } else { (Resolve-Path -LiteralPath (Join-Path $candidateRoot $Candidate)).Path }
if (-not $candidatePath.StartsWith((Resolve-Path $candidateRoot).Path + [IO.Path]::DirectorySeparatorChar)) { throw "Candidate must be inside Research/candidate-packages." }

$required = @("run-manifest.json", "claims.json", "rejected-claims.json", "source-registry.patch.json", "proposed-changes.md", "eval-plan.json", "report.md", "report.pdf", "promotion/manifest.json")
$missing = @($required | Where-Object { -not (Test-Path -LiteralPath (Join-Path $candidatePath $_)) })
if ($missing.Count -gt 0) { throw "Candidate is incomplete: $($missing -join ', ')" }
$manifest = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $candidatePath "promotion/manifest.json") | ConvertFrom-Json
Assert-PromotionManifest $manifest
if ($manifest.candidate_id -ne (Split-Path -Leaf $candidatePath)) { throw "Promotion candidate_id does not match directory." }
if ($manifest.status -ne "awaiting-approval") { throw "Candidate status must be awaiting-approval." }
$stablePath = Join-Path $rootPath "Runtime/stable/manifest.json"
$stableHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $stablePath).Hash
if ($stableHash -ne $manifest.stable_manifest_before_sha256) { throw "Stable manifest changed after candidate creation; rebase and re-evaluate." }

foreach ($eval in $manifest.required_evals) {
    $reportPath = Join-Path $candidatePath $eval.report
    if (-not (Test-Path -LiteralPath $reportPath)) { throw "Required eval report missing: $($eval.report)" }
    $report = Get-Content -Raw -Encoding UTF8 -LiteralPath $reportPath | ConvertFrom-Json
    if ([int]$report.passed -lt [int]$eval.minimum_passed -or [int]$report.failed -gt [int]$eval.maximum_failed) { throw "Eval gate failed: $($eval.report)" }
}

# The authoritative eval gate (release-gate.ps1 -Mode full) is enforced at
# -Approve time, not during the dry-run preview. Candidate-authored reports above
# are necessary but not sufficient; a candidate controls the numbers in its own
# directory, so promotion also requires the repo's own gate to pass.
$releaseGate = [ordered]@{ enforced = $false; passed = $null; report = $null; skipped_reason = $null; note = "release gate runs at -Approve" }

$forbiddenPrefixes = @(".git", ".claude/commands", "Research/candidate-packages", "Runtime/releases")
$validated = @()
foreach ($file in $manifest.files) {
    if ([IO.Path]::IsPathRooted($file.source) -or [IO.Path]::IsPathRooted($file.target) -or $file.source -match '(^|[\\/])\.\.([\\/]|$)' -or $file.target -match '(^|[\\/])\.\.([\\/]|$)') { throw "Absolute paths and traversal are forbidden in promotion manifests." }
    $normalizedTarget = $file.target.Replace('\','/')
    if (@($forbiddenPrefixes | Where-Object { $normalizedTarget -eq $_ -or $normalizedTarget.StartsWith($_ + "/") }).Count -gt 0) { throw "Forbidden promotion target: $normalizedTarget" }
    $source = (Resolve-Path -LiteralPath (Join-Path $candidatePath $file.source)).Path
    if (-not $source.StartsWith($candidatePath + [IO.Path]::DirectorySeparatorChar)) { throw "Promotion source escaped candidate." }
    $target = Join-Path $rootPath $file.target
    $after = (Get-FileHash -Algorithm SHA256 -LiteralPath $source).Hash
    if ($after -ne $file.after_sha256) { throw "Candidate payload hash mismatch: $($file.source)" }
    $exists = Test-Path -LiteralPath $target
    $before = if ($exists) { (Get-FileHash -Algorithm SHA256 -LiteralPath $target).Hash } else { $null }
    if ($before -ne $file.before_sha256) { throw "Target changed since candidate creation: $($file.target)" }
    $validated += [pscustomobject]@{ source=$source; target=$target; relative=$file.target; existed=$exists; before=$before; after=$after }
}

$preview = [ordered]@{ schema_version=1; candidate=$manifest.candidate_id; release=$manifest.release; approved=$false; release_gate=$releaseGate; files=@($validated | ForEach-Object { [ordered]@{ target=$_.relative; existed=$_.existed; before_sha256=$_.before; after_sha256=$_.after } }) }
if (-not $Approve) { $preview | ConvertTo-Json -Depth 8; exit 3 }
if (-not $ApprovedBy) { throw "-ApprovedBy is required with -Approve." }

# Fail-closed eval gate. release-gate.ps1 is this script's sibling (always the real
# tool, even when -Root points elsewhere) and validates the source repo it lives in.
# The skip path exists only for the human owner and is recorded in the promotion
# record so a bypass is never silent.
if ($SkipReleaseGate) {
    if ([string]::IsNullOrWhiteSpace($SkipReleaseGateReason)) { throw "-SkipReleaseGate requires -SkipReleaseGateReason (recorded in the promotion record)." }
    $releaseGate.skipped_reason = $SkipReleaseGateReason
    $releaseGate.note = "skipped by operator"
    Write-Warning "Release gate SKIPPED by operator: $SkipReleaseGateReason"
} else {
    $gateScript = Join-Path $PSScriptRoot "release-gate.ps1"
    if (-not (Test-Path -LiteralPath $gateScript)) { throw "release-gate.ps1 not found next to promote-candidate.ps1; refusing promotion." }
    $reportsDir = Join-Path (Split-Path -Parent $PSScriptRoot) "Evals/reports"
    if (-not (Test-Path -LiteralPath $reportsDir)) { New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null }
    $gateReportPath = Join-Path $reportsDir ("{0}-promotion-release-gate-full.json" -f (Get-Date -Format 'yyyy-MM-dd-HHmmss'))
    $oldPref = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & powershell -NoProfile -ExecutionPolicy Bypass -File $gateScript -Mode full -OutputPath $gateReportPath | Out-Null
    $gateExit = $LASTEXITCODE
    $ErrorActionPreference = $oldPref
    if (-not (Test-Path -LiteralPath $gateReportPath)) { throw "release-gate.ps1 produced no report; refusing promotion." }
    $gate = Get-Content -Raw -Encoding UTF8 -LiteralPath $gateReportPath | ConvertFrom-Json
    $releaseGate.enforced = $true
    $releaseGate.passed = [bool]$gate.passed
    $releaseGate.report = $gateReportPath
    $releaseGate.note = "release-gate.ps1 -Mode full"
    if ($gateExit -ne 0 -or -not $gate.passed) {
        $failedIds = @($gate.checks | Where-Object { -not $_.passed } | ForEach-Object { $_.id }) -join ', '
        throw "release-gate.ps1 -Mode full failed ($($gate.checks_failed) checks: $failedIds); refusing promotion. Report: $gateReportPath"
    }
}

$releasePath = Join-Path $rootPath ("Runtime/releases/{0}" -f $manifest.release)
if (Test-Path -LiteralPath $releasePath) { throw "Release already exists: $($manifest.release)" }
New-Item -ItemType Directory -Force -Path (Join-Path $releasePath "rollback") | Out-Null
$rollbackFiles = @()
foreach ($item in $validated) {
    if ($item.existed) {
        $backup = Join-Path $releasePath ("rollback/{0}" -f $item.relative)
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $backup) | Out-Null
        Copy-Item -LiteralPath $item.target -Destination $backup -Force
    }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $item.target) | Out-Null
    Copy-Item -LiteralPath $item.source -Destination $item.target -Force
    $rollbackFiles += [ordered]@{ target=$item.relative; existed_before=$item.existed; restore_source=if($item.existed){"rollback/$($item.relative)"}else{$null}; promoted_sha256=$item.after; previous_sha256=$item.before }
}
$record = [ordered]@{ schema_version=1; release=$manifest.release; candidate=$manifest.candidate_id; promoted_at=(Get-Date).ToString('o'); approved_by=$ApprovedBy; release_gate=$releaseGate; files=$rollbackFiles }
$record | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $releasePath "promotion-record.json")
$record | ConvertTo-Json -Depth 8
