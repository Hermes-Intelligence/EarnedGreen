[CmdletBinding()]
param([string]$OutputPath)

$ErrorActionPreference = "Stop"
if (-not $OutputPath) { $OutputPath = Join-Path $PSScriptRoot "claude-v1-migration.json" }
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$inputs = @(
    "Claude/OPERATING_CONTRACT.md",
    "Codex/OPERATING_CONTRACT.md",
    "Research/knowledge-base/2026-07-12-findings.md",
    "Research Outputs/2026-07-12/report.md"
)

function Get-Tier([uri]$Uri) {
    $domain = $Uri.Host.ToLowerInvariant()
    if ($domain -in @("openai.com", "www.openai.com", "developers.openai.com", "learn.chatgpt.com", "platform.openai.com", "anthropic.com", "www.anthropic.com", "code.claude.com", "platform.claude.com") -or
        ($domain -eq "github.com" -and $Uri.AbsolutePath.StartsWith("/openai/"))) { return 1 }
    if ($domain -eq "arxiv.org") { return 2 }
    if ($domain -in @("cognition.ai", "sourcegraph.com", "sophos.com", "www.sophos.com", "helpnetsecurity.com", "modal.com", "northflank.com", "tembo.io")) { return 3 }
    return 5
}

function Get-Type([uri]$Uri, [int]$Tier) {
    if ($Uri.Host -eq "arxiv.org") { return "primary-paper" }
    if ($Tier -eq 1) { return "official-docs-or-engineering" }
    if ($Tier -eq 3) { return "vendor-or-security-engineering" }
    return "practitioner-or-secondary"
}

$found = [ordered]@{}
foreach ($relative in $inputs) {
    $path = Join-Path $root $relative
    if (-not (Test-Path -LiteralPath $path)) { continue }
    $content = Get-Content -Raw -Encoding UTF8 -LiteralPath $path
    foreach ($match in [regex]::Matches($content, 'https?://[^\s\)\]<>"'']+')) {
        $url = $match.Value.TrimEnd('.', ',', ';', ':')
        try { $uri = [uri]$url } catch { continue }
        if (-not $found.Contains($url)) {
            $tier = Get-Tier $uri
            $slug = (($uri.Host + $uri.AbsolutePath).ToLowerInvariant() -replace '^www\.', '' -replace '[^a-z0-9]+', '-').Trim('-')
            if ($slug.Length -gt 72) { $slug = $slug.Substring(0, 72).TrimEnd('-') }
            $found[$url] = [ordered]@{
                id = "claude-v1-$slug"
                title = "Claude v1 discovery: $($uri.Host)$($uri.AbsolutePath)"
                url = $url
                type = Get-Type $uri $tier
                tier = $tier
                status = "pending-review"
                topics = @("claude-v1-discovery")
                discovered_at = "2026-07-12"
                discovered_in = @($relative)
                last_checked = $null
                next_check = "2026-07-12"
                notes = "Preserved from Claude's original corpus. Must pass link, relevance, provenance and claim-level review before active use."
            }
        } else {
            $existing = $found[$url]
            if ($relative -notin $existing.discovered_in) { $existing.discovered_in += $relative }
        }
    }
}

$items = @($found.Values | Sort-Object url)
$ids = @{}
foreach ($item in $items) {
    $base = $item.id; $candidate = $base; $n = 2
    while ($ids.ContainsKey($candidate)) { $candidate = "$base-$n"; $n++ }
    $item.id = $candidate; $ids[$candidate] = $true
}

$document = [ordered]@{
    schema_version = 1
    generated_at = (Get-Date).ToString("o")
    provenance = "Mechanical recovery from Claude v1 artifacts; no source is promoted by this migration."
    source_files = $inputs
    sources = $items
}
$document | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $OutputPath -Encoding UTF8
Write-Output ($document | ConvertTo-Json -Depth 8)
