[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$Release, [switch]$Approve, [string]$ApprovedBy, [string]$Root)
$ErrorActionPreference = "Stop"
if (-not $Root) { $Root = Split-Path -Parent $PSScriptRoot }
$rootPath = (Resolve-Path -LiteralPath $Root).Path
$releasePath = Join-Path $rootPath "Runtime/releases/$Release"
$recordPath = Join-Path $releasePath "promotion-record.json"
if (-not (Test-Path -LiteralPath $recordPath)) { throw "Unknown release: $Release" }
$record = Get-Content -Raw -Encoding UTF8 -LiteralPath $recordPath | ConvertFrom-Json
foreach ($file in $record.files) {
    $target = Join-Path $rootPath $file.target
    if (-not (Test-Path -LiteralPath $target)) { throw "Promoted target missing: $($file.target)" }
    $current = (Get-FileHash -Algorithm SHA256 -LiteralPath $target).Hash
    if ($current -ne $file.promoted_sha256) { throw "Refusing rollback because target changed after promotion: $($file.target)" }
}
$preview = [ordered]@{ schema_version=1; release=$Release; rollback_ready=$true; files=@($record.files.target) }
if (-not $Approve) { $preview | ConvertTo-Json -Depth 6; exit 3 }
if (-not $ApprovedBy) { throw "-ApprovedBy is required with -Approve." }
foreach ($file in $record.files) {
    $target = Join-Path $rootPath $file.target
    if ($file.existed_before) {
        $source = Join-Path $releasePath $file.restore_source
        if (-not (Test-Path -LiteralPath $source)) { throw "Rollback backup missing: $($file.restore_source)" }
        Copy-Item -LiteralPath $source -Destination $target -Force
    } else { Remove-Item -LiteralPath $target -Force }
}
[ordered]@{ schema_version=1; release=$Release; rolled_back_at=(Get-Date).ToString('o'); approved_by=$ApprovedBy } | ConvertTo-Json | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $releasePath "rollback-record.json")
Get-Content -Raw -LiteralPath (Join-Path $releasePath "rollback-record.json")
