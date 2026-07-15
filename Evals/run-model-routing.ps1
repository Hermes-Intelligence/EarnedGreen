[CmdletBinding()]
param([string]$OutputPath)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$cases = (Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $root "Evals/model-routing-cases.json") | ConvertFrom-Json).cases
$results = @()
foreach ($case in $cases) {
    if ($case.task) {
        $route = (& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root "tools/route.ps1") -Task $case.task -Repo $root -NoWrite) | ConvertFrom-Json
        $actual = $route.model_routing.capability_profile
        $passed = $actual -eq $case.expected_profile
        $results += [pscustomobject]@{ id=$case.id; passed=$passed; expected=$case.expected_profile; actual=$actual }
    } else {
        $args = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $root "tools/model-route.ps1"), "-Provider", $case.provider, "-Profile", $case.profile)
        if ($case.risk) { $args += @("-Risk", $case.risk) }
        if ($case.explicit_selector) { $args += @("-ExplicitSelector", $case.explicit_selector) }
        if ($case.expected_error) {
            $previousErrorPreference = $ErrorActionPreference
            $ErrorActionPreference = "Continue"
            $output = & powershell @args 2>&1 | Out-String
            $childExitCode = $LASTEXITCODE
            $ErrorActionPreference = $previousErrorPreference
            $normalizedOutput = ($output -replace '\s+', ' ').Trim()
            $normalizedExpected = ([string]$case.expected_error -replace '\s+', ' ').Trim()
            $passed = $childExitCode -ne 0 -and $normalizedOutput.Contains($normalizedExpected)
            $results += [pscustomobject]@{ id=$case.id; passed=$passed; expected_error=$case.expected_error; rejected=($childExitCode -ne 0) }
        } else {
            $route = (& powershell @args) | ConvertFrom-Json
            $passed = $route.selector -eq $case.expected_selector -and $route.recommendation_only
            $results += [pscustomobject]@{ id=$case.id; passed=$passed; expected=$case.expected_selector; actual=$route.selector; recommendation_only=$route.recommendation_only }
        }
    }
}
$failed = @($results | Where-Object { -not $_.passed }).Count
$report = [ordered]@{ schema_version=1; run_at=(Get-Date).ToString("o"); scope="deterministic profile routing only; not outcome quality"; cases=$results.Count; passed=$results.Count-$failed; failed=$failed; results=$results }
if (-not $OutputPath) { $OutputPath = Join-Path $root ("Evals/reports/{0}-model-routing.json" -f (Get-Date).ToString("yyyy-MM-dd-HHmmss")) }
$report | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 -LiteralPath $OutputPath
$report | ConvertTo-Json -Depth 8
if ($failed -gt 0) { exit 1 }
