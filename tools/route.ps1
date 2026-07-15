[CmdletBinding()]
param(
    [string]$Task,
    [string]$Repo = (Get-Location).Path,
    [string[]]$ChangedPath = @(),
    [string]$CatalogPath,
    [string]$OutputPath,
    [switch]$NoWrite,
    [switch]$Adaptive,
    [string]$TaskFile,
    [ValidateSet('vanilla','mode-1-lean','mode-2-routed','mode-3-assured','full')][string]$ForceMode
)

$ErrorActionPreference = "Stop"
$sourceRoot = Split-Path -Parent $PSScriptRoot

# ---------------------------------------------------------------------------
# Adaptive path (additive, promoted from candidate 2026-07-14-adaptive-agent-
# modes-v2). The classic keyword router below is untouched and remains the
# default; -Adaptive shells to tools/adaptive/prepare_or_route.py and returns
# its JSON. The mode ladder is a COST ladder plus governance controls (human
# gate on critical consequence, durable checkpoints, spec-freeze); it is NOT a
# correctness-lift claim - see Setup/adaptive-modes.md.
# ---------------------------------------------------------------------------
if ($Adaptive) {
    if (-not $Task -and -not $TaskFile) { throw "-Adaptive requires -Task or -TaskFile." }
    $python = Get-Command python -ErrorAction SilentlyContinue
    $prefix = @()
    if ($python) {
        $pythonExe = $python.Source
    } else {
        $py = Get-Command py -ErrorAction SilentlyContinue
        if (-not $py) { throw "The adaptive path needs a Python 3 interpreter ('python' or the Windows 'py' launcher) on PATH; none was found. Install Python 3.11+ or use the classic path (omit -Adaptive)." }
        $pythonExe = $py.Source
        $prefix = @('-3')
    }
    $repoPath = (Resolve-Path -LiteralPath $Repo).Path
    $pyArgs = @((Join-Path $sourceRoot 'tools/adaptive/prepare_or_route.py'), '--workspace', $repoPath)
    if ($TaskFile) { $pyArgs += @('--task-file', $TaskFile) } else { $pyArgs += @('--task', $Task) }
    foreach ($path in $ChangedPath) { $pyArgs += @('--changed-path', $path) }
    if ($ForceMode) { $pyArgs += @('--force-mode', $ForceMode) }
    if ($NoWrite) {
        $pyArgs += '--route-only'
    } else {
        if (-not $OutputPath) { $OutputPath = Join-Path $repoPath '.agentic' }
        $output = [IO.Path]::GetFullPath($OutputPath)
        if (-not ($output -eq (Join-Path $repoPath '.agentic') -or $output.StartsWith($repoPath + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase))) { throw 'Adaptive context output must remain inside the target repository.' }
        $pyArgs += @('--output-dir', $output)
    }
    & $pythonExe @prefix @pyArgs
    exit $LASTEXITCODE
}

if (-not $Task) { throw "-Task is required." }
if ($ForceMode) { throw "-ForceMode is only valid with -Adaptive." }
if (-not $CatalogPath) { $CatalogPath = Join-Path $sourceRoot "Router/catalog/modules.json" }
$catalog = Get-Content -Raw -Encoding UTF8 -LiteralPath $CatalogPath | ConvertFrom-Json
$text = $Task.ToLowerInvariant()

function Test-Term([string]$value, [string]$term) {
    $lower = $term.ToLowerInvariant()
    if ($lower.Contains(" ")) {
        $words = @($lower -split '\s+' | Where-Object { $_ } | ForEach-Object { [regex]::Escape($_) })
        $phrase = $words -join '\s+'
        return [regex]::IsMatch($value, "(?<![a-z0-9_-])(?:$phrase)(?![a-z0-9_-])")
    }
    $variants = @($lower)
    if ($lower -match '[^aeiou]y$') { $variants += ($lower.Substring(0, $lower.Length - 1) + 'ies') }
    elseif ($lower -match '(s|x|z|ch|sh)$') { $variants += ($lower + 'es') }
    else { $variants += ($lower + 's') }
    $pattern = @($variants | Sort-Object -Unique | ForEach-Object { [regex]::Escape($_) }) -join '|'
    return [regex]::IsMatch($value, "(?<![a-z0-9_-])(?:$pattern)(?![a-z0-9_-])")
}

function Test-Any([string]$value, [string[]]$needles) {
    foreach ($needle in $needles) { if (Test-Term $value $needle) { return $true } }
    return $false
}

$taskType = if (Test-Any $text @("bug", "fix", "error", "regression")) { "bugfix" }
    elseif (Test-Any $text @("refactor", "rename", "restructure")) { "refactor" }
    elseif (Test-Any $text @("research", "investigate", "compare")) { "research" }
    elseif (Test-Any $text @("review", "audit")) { "review" }
    elseif (Test-Any $text @("migrate", "migration")) { "migration" }
    else { "feature-or-change" }

$riskFactors = New-Object System.Collections.Generic.List[string]
$riskMap = [ordered]@{
    "security" = @("auth", "authentication", "authorization", "login", "password", "permission", "secret", "credential", "api token", "access token", "auth token", "prompt injection")
    "payments" = @("payment", "stripe", "billing", "webhook")
    "production" = @("production", "deploy", "release", "outward-facing")
    "data-loss" = @("delete data", "drop table", "destructive", "migration", "backfill")
    "external-side-effects" = @("send", "publish", "network")
}
foreach ($entry in $riskMap.GetEnumerator()) { if (Test-Any $text $entry.Value) { $riskFactors.Add($entry.Key) } }
$risk = if ($riskFactors -contains "security" -or $riskFactors -contains "payments" -or $riskFactors -contains "data-loss") { "high" }
    elseif ($riskFactors.Count -gt 0) { "medium" } else { "low" }

$mechanicalLowRisk = $risk -eq "low" -and (Test-Any $text @("mechanical", "private local", "deterministic checks", "format", "typo"))
$modelProfile = if ($mechanicalLowRisk) { "fast-low-risk" }
    elseif ($taskType -eq "research") { "research-synthesizer" }
    elseif ($taskType -eq "review" -and $risk -eq "high") { "adversarial-review" }
    elseif ($risk -eq "high") { "architecture-high-risk" }
    elseif ($taskType -in @("refactor", "migration", "bugfix")) { "deep-implementation" }
    else { "balanced-daily" }

$scored = @()
foreach ($module in $catalog.modules) {
    $score = if ($module.always) { 1000 } else { 0 }
    $reasons = New-Object System.Collections.Generic.List[string]
    if ($module.always) { $reasons.Add("always-on routed gate") }
    foreach ($keyword in $module.keywords) {
        if (Test-Term $text $keyword) { $score += 3; $reasons.Add("task keyword: $keyword") }
    }
    foreach ($path in $ChangedPath) {
        $normPath = $path -replace '\\', '/'
        foreach ($pattern in $module.path_patterns) {
            if ($normPath -like $pattern) { $score += 2; $reasons.Add("path match: $pattern") }
        }
    }
    # Security favors recall: security/payments always pull the security module, and
    # destructive data operations (data-loss factor: migration/backfill/drop/delete data)
    # do too. The data-loss keywords are qualified phrases, so benign edits like
    # "delete the unused import" do not match and do not load security.
    if ($module.id -eq "security-boundaries" -and ($riskFactors -contains "security" -or $riskFactors -contains "payments" -or $riskFactors -contains "data-loss")) { $score += 10; $reasons.Add("risk factor recall: security/payments/data-loss") }
    if ($module.id -eq "database-migration" -and $riskFactors -contains "data-loss") { $score += 10; $reasons.Add("risk factor: data-loss") }
    if ($score -gt 0) {
        $scored += [pscustomobject]@{ module = $module; score = $score; reasons = @($reasons) }
    }
}

$sorted = @($scored | Sort-Object @{Expression={-$_.score}}, @{Expression={-$_.module.priority}}, @{Expression={$_.module.id}})
$maxModules = $catalog.context_budget.max_modules
$hardLimit = $catalog.context_budget.hard_limit_characters
$selected = @()
$totalCharacters = 0
foreach ($item in $sorted) {
    if ($selected.Count -ge $maxModules) { break }
    $isAlways = [bool]$item.module.always
    $moduleSize = 0
    $modulePath = Join-Path $sourceRoot $item.module.path
    if (Test-Path -LiteralPath $modulePath) { $moduleSize = (Get-Item -LiteralPath $modulePath).Length }
    if (-not $isAlways -and $hardLimit -and (($totalCharacters + $moduleSize) -gt $hardLimit)) { break }
    $totalCharacters += $moduleSize
    $selected += $item
}
$selected = @($selected)
$rejected = @($catalog.modules | Where-Object { $_.id -notin @($selected.module.id) } | ForEach-Object { $_.id })

# Confidence derives from match strength, not module count.
$nonAlwaysScores = @($selected | Where-Object { -not $_.module.always } | ForEach-Object { $_.score })
$topScore = if ($nonAlwaysScores.Count -gt 0) { ($nonAlwaysScores | Measure-Object -Maximum).Maximum } else { 0 }
$riskModuleLoaded = @($selected | Where-Object { $_.module.id -in @("security-boundaries", "database-migration") }).Count -gt 0
$riskAligned = ($riskFactors.Count -gt 0 -and $riskModuleLoaded)
$routingConfidence = if (($topScore -ge 6 -and $riskAligned) -or $topScore -ge 9) { "high" }
    elseif ($topScore -ge 3) { "medium" }
    else { "low" }
$pack = [ordered]@{
    schema_version = 1
    generated_at = (Get-Date).ToString("o")
    task = $Task
    repo = (Resolve-Path -LiteralPath $Repo).Path
    fingerprint = [ordered]@{
        task_type = $taskType
        risk = $risk
        risk_factors = @($riskFactors)
        changed_paths = @($ChangedPath)
    }
    core = "Core/runtime.md"
    selected_modules = @($selected | ForEach-Object { [ordered]@{ id=$_.module.id; path=$_.module.path; score=$_.score; reasons=$_.reasons } })
    rejected_modules = $rejected
    context_budget = $catalog.context_budget
    selected_characters = $totalCharacters
    model_routing = [ordered]@{
        capability_profile = $modelProfile
        recommendation_only = $true
        note = "Resolve through tools/model-route.ps1; never persist the user's default model."
    }
    routing_confidence = $routingConfidence
}

$json = $pack | ConvertTo-Json -Depth 10
if (-not $NoWrite) {
    if (-not $OutputPath) { $OutputPath = Join-Path $sourceRoot "Runtime/session/context-pack.json" }
    $parent = Split-Path -Parent $OutputPath
    if (-not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
    Set-Content -LiteralPath $OutputPath -Value $json -Encoding UTF8
}
$json
