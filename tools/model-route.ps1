[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateSet("anthropic-claude-code", "openai-codex")][string]$Provider,
    [Parameter(Mandatory = $true)][string]$Profile,
    [ValidateSet("low", "medium", "high", "critical")][string]$Risk = "low",
    [string]$ExplicitSelector,
    [string]$ProfilesPath,
    [string]$ProvidersPath
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
if (-not $ProfilesPath) { $ProfilesPath = Join-Path $root "Models/profiles.json" }
if (-not $ProvidersPath) { $ProvidersPath = Join-Path $root "Models/providers.json" }
$profiles = Get-Content -Raw -Encoding UTF8 -LiteralPath $ProfilesPath | ConvertFrom-Json
$catalog = Get-Content -Raw -Encoding UTF8 -LiteralPath $ProvidersPath | ConvertFrom-Json
$profileDef = @($profiles.profiles | Where-Object id -eq $Profile)[0]
$providerDef = @($catalog.providers | Where-Object id -eq $Provider)[0]
if (-not $profileDef) { throw "Unknown capability profile: $Profile" }
if (-not $providerDef) { throw "Unknown provider: $Provider" }
$riskRank = @{ low=1; medium=2; high=3; critical=4 }
if ($riskRank[$Risk] -gt $riskRank[[string]$profileDef.max_risk]) { throw "Profile '$Profile' is not permitted for risk '$Risk'; select a profile with an adequate risk floor." }
$expired = [datetimeoffset]::Now -gt ([datetimeoffset]$catalog.expires_at)
$candidates = @($providerDef.selectors | Where-Object { $Profile -in $_.profiles })
if ($ExplicitSelector) {
    $selected = @($providerDef.selectors | Where-Object id -eq $ExplicitSelector)[0]
    if (-not $selected) { throw "Explicit selector '$ExplicitSelector' is not present in the current provider catalog." }
    if ($Profile -notin $selected.profiles) { throw "Explicit selector '$ExplicitSelector' does not satisfy capability profile '$Profile'." }
    $reason = "explicit user selector; capability profile retained for evidence"
} else {
    $selected = $candidates | Select-Object -First 1
    $reason = "first eligible provider selector for stable capability profile"
}
if (-not $selected) { throw "No selector currently satisfies profile '$Profile' for '$Provider'." }
[ordered]@{
    schema_version = 1; recommendation_only = $true; provider = $Provider; capability_profile = $Profile; risk = $Risk
    selector = $selected.id; selector_kind = $selected.kind; effort = $profileDef.effort; human_gate = [bool]$profileDef.human_gate
    catalog_generated_at = $catalog.generated_at; catalog_expires_at = $catalog.expires_at; catalog_expired = $expired; reason = $reason
    instruction = if ($expired -and -not $ExplicitSelector) { "Refresh candidate catalog or resolve a provider-native current alias; do not invent a model ID." } else { "Apply only to this task/session/subagent and record the actual resolved model after execution." }
    official_sources = @($providerDef.official_sources)
} | ConvertTo-Json -Depth 8
