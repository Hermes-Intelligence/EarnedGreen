[CmdletBinding()]
param(
    [string]$RunId = ((Get-Date).ToString("yyyy-MM-dd-HHmmss")),
    [string[]]$Topics = @()
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$candidate = Join-Path $root "Research/candidate-packages/$RunId"
if (Test-Path -LiteralPath $candidate) { throw "Candidate already exists: $candidate" }
New-Item -ItemType Directory -Path $candidate | Out-Null

$registryPath = Join-Path $root "Research/sources/registry.json"
$registry = Get-Content -Raw -Encoding UTF8 -LiteralPath $registryPath | ConvertFrom-Json
$migrationPath = Join-Path $root "Research/sources/claude-v1-migration.json"
$migration = if (Test-Path -LiteralPath $migrationPath) { Get-Content -Raw -Encoding UTF8 -LiteralPath $migrationPath | ConvertFrom-Json } else { [pscustomobject]@{ sources=@() } }
function Get-NormalizedUrl([string]$url) {
    $uri = [uri]$url
    $builder = [System.UriBuilder]::new($uri)
    $builder.Fragment = ""
    $builder.Host = $builder.Host.ToLowerInvariant()
    if ($builder.Path.EndsWith("/") -and $builder.Path -ne "/") { $builder.Path = $builder.Path.TrimEnd("/") }
    return $builder.Uri.AbsoluteUri.TrimEnd('/')
}
$sourceMap = [ordered]@{}
foreach ($source in @($registry.sources) + @($migration.sources)) {
    $key = Get-NormalizedUrl $source.url
    if (-not $sourceMap.Contains($key) -or $source.status -eq "active") { $sourceMap[$key] = $source }
}
$sourceSnapshot = [ordered]@{
    schema_version = 1
    generated_at = (Get-Date).ToString("o")
    source_inventories = @("Research/sources/registry.json", "Research/sources/claude-v1-migration.json")
    sources = @($sourceMap.Values)
}
$today = (Get-Date).Date
$due = @($sourceSnapshot.sources | Where-Object { $_.status -eq "pending-review" -or ($_.status -eq "active" -and ([datetime]$_.next_check).Date -le $today) })

$manifest = [ordered]@{
    schema_version = 1
    run_id = $RunId
    status = "candidate-initialized"
    created_at = (Get-Date).ToString("o")
    topics = @($Topics)
    stable_manifest_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $root "Runtime/stable/manifest.json")).Hash
    stable_paths_writable = $false
    direct_commit_or_push_allowed = $false
    source_registries = @("Research/sources/registry.json", "Research/sources/claude-v1-migration.json")
    due_source_ids = @($due.id)
    required_artifacts = @("run-manifest.json", "source-registry-snapshot.json", "claims.json", "rejected-claims.json", "source-registry.patch.json", "proposed-changes.md", "eval-plan.json", "report.md", "report.pdf")
}
$manifest | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $candidate "run-manifest.json")
$sourceSnapshot | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $candidate "source-registry-snapshot.json")
@() | ConvertTo-Json | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $candidate "claims.json")
@() | ConvertTo-Json | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $candidate "rejected-claims.json")
@{ add=@(); update=@(); retire=@() } | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $candidate "source-registry.patch.json")
@{ required_eval_arms=@("vanilla", "core", "core-router", "core-router-enforcement"); cases=@(); status="pending" } | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $candidate "eval-plan.json")
Set-Content -Encoding UTF8 -LiteralPath (Join-Path $candidate "proposed-changes.md") -Value "# Proposed Changes`r`n`r`nNo stable changes have been proposed yet.`r`n"
Set-Content -Encoding UTF8 -LiteralPath (Join-Path $candidate "report.md") -Value "# Research Candidate $RunId`r`n`r`nStatus: initialized. This candidate is not stable guidance.`r`n`r`n## Sources`r`n`r`nThe completed report must list every used source as a clickable Markdown link.`r`n"
Write-Output $candidate
