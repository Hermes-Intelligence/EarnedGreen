[CmdletBinding()]
param([string]$ProvidersPath)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
if (-not $ProvidersPath) { $ProvidersPath = Join-Path $root "Models/providers.json" }
$catalog = Get-Content -Raw -Encoding UTF8 -LiteralPath $ProvidersPath | ConvertFrom-Json
[ordered]@{
    schema_version = 1; candidate_only = $true; due = [datetimeoffset]::Now -ge ([datetimeoffset]$catalog.expires_at)
    current_generated_at = $catalog.generated_at; current_expires_at = $catalog.expires_at
    providers = @($catalog.providers | ForEach-Object { [ordered]@{ id=$_.id; discovery=$_.discovery; official_sources=$_.official_sources } })
    required_checks = @("query current availability", "verify official documentation", "check CLI/API version gates", "run routing tests", "run outcome A/B before promotion")
    forbidden_action = "Do not modify Models/providers.json or stable rules from research; emit a candidate patch."
} | ConvertTo-Json -Depth 8
