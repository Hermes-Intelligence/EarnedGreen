[CmdletBinding()]
param(
    [ValidateSet("routing", "validate")][string]$Mode = "routing",
    [string]$CasesPath = "Evals/cases.json",
    [string]$OutputPath
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$cases = (Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $root $CasesPath) | ConvertFrom-Json).cases
$results = @()

foreach ($case in $cases) {
    if ($Mode -eq "validate") {
        $passed = $case.id -and $case.task -and $case.required_modules -and $case.hidden_grader
        $results += [pscustomobject]@{ id=$case.id; passed=[bool]$passed; missing=@() }
        continue
    }
    $routeText = & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root "tools/route.ps1") -Task $case.task -Repo $root -NoWrite
    $route = $routeText | ConvertFrom-Json
    $selected = @($route.selected_modules.id)
    $missing = @($case.required_modules | Where-Object { $_ -notin $selected })
    $forbidden = @($case.forbidden_modules | Where-Object { $_ -in $selected })
    $results += [pscustomobject]@{
        id = $case.id
        passed = ($missing.Count -eq 0 -and $forbidden.Count -eq 0)
        selected = $selected
        missing = $missing
        forbidden_selected = $forbidden
        confidence = $route.routing_confidence
    }
}

$failed = @($results | Where-Object { -not $_.passed }).Count
$report = [ordered]@{
    schema_version=1
    run_at=(Get-Date).ToString("o")
    mode=$Mode
    cases=$results.Count
    passed=$results.Count-$failed
    failed=$failed
    results=$results
}
if (-not $OutputPath) { $OutputPath = Join-Path $root ("Evals/reports/{0}-routing.json" -f (Get-Date).ToString("yyyy-MM-dd-HHmmss")) }
$report | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 -LiteralPath $OutputPath
$report | ConvertTo-Json -Depth 10
if ($failed -gt 0) { exit 1 }
exit 0
