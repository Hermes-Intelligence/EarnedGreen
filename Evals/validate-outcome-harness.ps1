[CmdletBinding()]
param(
    [string]$OutputPath,
    [Alias('Fixture')][string]$FixtureId,
    [ValidateRange(1, 120)][int]$PhaseTimeoutSeconds = 15
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = (Get-Command python -ErrorAction Stop).Source
$catalog = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $root "Evals/fixtures/catalog.json") | ConvertFrom-Json
$fixtures = @($catalog.fixtures)
if ($FixtureId) {
    $fixtures = @($fixtures | Where-Object { $_.id -eq $FixtureId })
    if ($fixtures.Count -ne 1) { throw "Unknown or duplicate fixture id: $FixtureId" }
}
$results = @()

function Invoke-PythonPhase([string[]]$Arguments, [string]$WorkingDirectory, [int]$TimeoutSeconds) {
    $quoted = @($Arguments | ForEach-Object { '"' + ([string]$_).Replace('"', '\"') + '"' })
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $python
    $startInfo.Arguments = $quoted -join " "
    $startInfo.WorkingDirectory = $WorkingDirectory
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $startInfo
    try {
        if (-not $process.Start()) { throw "Python process did not start" }
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        $finished = $process.WaitForExit($TimeoutSeconds * 1000)
        if (-not $finished) {
            try { $process.Kill() } catch {}
        }
        $process.WaitForExit()
        $process.Refresh()
        $out = $stdoutTask.Result
        $err = $stderrTask.Result
        [pscustomobject]@{
            completed = $finished
            exit_code = $(if ($finished) { [int]$process.ExitCode } else { 124 })
            output = (($out + $err).Trim() | Select-Object -First 1)
        }
    } finally {
        $process.Dispose()
    }
}

function Get-PhaseJson($Phase) {
    if (-not $Phase.completed -or -not $Phase.output) { return $null }
    $lines = @(([string]$Phase.output).Trim().Split([Environment]::NewLine))
    for ($index = $lines.Count - 1; $index -ge 0; $index--) {
        try { return ($lines[$index] | ConvertFrom-Json) } catch {}
    }
    return $null
}

foreach ($fixture in $fixtures) {
    $temp = Join-Path ([IO.Path]::GetTempPath()) ("fixture-" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $temp | Out-Null
    try {
        $publicRoot = Join-Path $root $fixture.public_path
        $grader = Join-Path $root $fixture.hidden_grader
        $referenceRoot = Join-Path (Split-Path -Parent $grader) "reference"
        $structureOk = (Test-Path -LiteralPath (Join-Path $publicRoot $fixture.task_file)) -and (Test-Path -LiteralPath $grader) -and (Test-Path -LiteralPath $referenceRoot)
        if ($structureOk) { Copy-Item -Path (Join-Path $publicRoot "*") -Destination $temp -Recurse -Force }

        $publicArgs = @($fixture.public_test | Select-Object -Skip 1)
        $starterPublic = if ($structureOk) { Invoke-PythonPhase $publicArgs $temp $PhaseTimeoutSeconds } else { [pscustomobject]@{completed=$true;exit_code=2;output="fixture structure incomplete"} }
        $starterHidden = if ($structureOk) { Invoke-PythonPhase @($grader, $temp) $temp $PhaseTimeoutSeconds } else { [pscustomobject]@{completed=$true;exit_code=2;output="fixture structure incomplete"} }

        $starterHiddenJson = Get-PhaseJson $starterHidden
        $starterScore = if ($starterHiddenJson -and $starterHiddenJson.PSObject.Properties.Name -contains 'score') { [double]$starterHiddenJson.score } else { $null }
        $negativeControlResults = @()
        $controlDefinitions = if ($fixture.PSObject.Properties.Name -contains 'negative_controls') { @($fixture.negative_controls) } else { @() }
        foreach ($control in $controlDefinitions) {
            $controlTemp = Join-Path ([IO.Path]::GetTempPath()) ("fixture-control-" + [guid]::NewGuid().ToString("N"))
            New-Item -ItemType Directory -Path $controlTemp | Out-Null
            try {
                Copy-Item -Path (Join-Path $publicRoot "*") -Destination $controlTemp -Recurse -Force
                $controlRoot = Join-Path $root $control.path
                if (Test-Path -LiteralPath $controlRoot) { Copy-Item -Path (Join-Path $controlRoot "*") -Destination $controlTemp -Recurse -Force }
                $controlPublic = Invoke-PythonPhase $publicArgs $controlTemp $PhaseTimeoutSeconds
                $controlHidden = Invoke-PythonPhase @($grader, $controlTemp) $controlTemp $PhaseTimeoutSeconds
                $controlJson = Get-PhaseJson $controlHidden
                $controlScore = if ($controlJson -and $controlJson.PSObject.Properties.Name -contains 'score') { [double]$controlJson.score } else { $null }
                $controlPassed = (Test-Path -LiteralPath $controlRoot) -and $controlPublic.exit_code -eq 0 -and $controlHidden.exit_code -ne 0 -and $null -ne $controlScore -and $controlScore -le [double]$control.expected_max_score
                $negativeControlResults += [pscustomobject]@{id=$control.id;public_passed=($controlPublic.exit_code -eq 0);hidden_rejected=($controlHidden.exit_code -ne 0);score=$controlScore;expected_max_score=[double]$control.expected_max_score;passed=$controlPassed}
            } finally {
                if (Test-Path -LiteralPath $controlTemp) { Remove-Item -LiteralPath $controlTemp -Recurse -Force }
            }
        }

        if ($structureOk) { Copy-Item -Path (Join-Path $referenceRoot "*") -Destination $temp -Recurse -Force }
        $referencePublic = if ($structureOk) { Invoke-PythonPhase $publicArgs $temp $PhaseTimeoutSeconds } else { [pscustomobject]@{completed=$true;exit_code=2;output="fixture structure incomplete"} }
        $referenceHidden = if ($structureOk) { Invoke-PythonPhase @($grader, $temp) $temp $PhaseTimeoutSeconds } else { [pscustomobject]@{completed=$true;exit_code=2;output="fixture structure incomplete"} }

        $referenceHiddenJson = Get-PhaseJson $referenceHidden
        $referenceScore = if ($referenceHiddenJson -and $referenceHiddenJson.PSObject.Properties.Name -contains 'score') { [double]$referenceHiddenJson.score } else { $null }

        # Optional second reference implementation. When hidden/reference-alt/
        # exists it must ALSO be accepted at the expected score. A grader that
        # only passes because ONE reference was authored to match brittle
        # literals (substrings, exact serialization, one HTML byte form) will
        # fail here, because the alt is a semantically-equivalent paraphrase.
        $referenceAltRoot = Join-Path (Split-Path -Parent $grader) "reference-alt"
        $referenceAltPresent = $structureOk -and (Test-Path -LiteralPath $referenceAltRoot)
        $referenceAltScore = $null
        $referenceAltPassed = $true
        if ($referenceAltPresent) {
            $altTemp = Join-Path ([IO.Path]::GetTempPath()) ("fixture-alt-" + [guid]::NewGuid().ToString("N"))
            New-Item -ItemType Directory -Path $altTemp | Out-Null
            try {
                Copy-Item -Path (Join-Path $publicRoot "*") -Destination $altTemp -Recurse -Force
                Copy-Item -Path (Join-Path $referenceAltRoot "*") -Destination $altTemp -Recurse -Force
                $altPublic = Invoke-PythonPhase $publicArgs $altTemp $PhaseTimeoutSeconds
                $altHidden = Invoke-PythonPhase @($grader, $altTemp) $altTemp $PhaseTimeoutSeconds
                $altJson = Get-PhaseJson $altHidden
                $referenceAltScore = if ($altJson -and $altJson.PSObject.Properties.Name -contains 'score') { [double]$altJson.score } else { $null }
                $expectedAlt = if ($fixture.PSObject.Properties.Name -contains 'reference_alt_expected_score') { [double]$fixture.reference_alt_expected_score } elseif ($fixture.PSObject.Properties.Name -contains 'reference_expected_score') { [double]$fixture.reference_expected_score } else { 100 }
                $referenceAltPassed = ($altPublic.exit_code -eq 0) -and ($altHidden.exit_code -eq 0) -and ($null -ne $referenceAltScore) -and ($referenceAltScore -eq $expectedAlt)
            } finally {
                if (Test-Path -LiteralPath $altTemp) { Remove-Item -LiteralPath $altTemp -Recurse -Force }
            }
        }

        $scoreContractPassed = $true
        if ($fixture.PSObject.Properties.Name -contains 'starter_expected_max_score') { $scoreContractPassed = $scoreContractPassed -and $null -ne $starterScore -and $starterScore -le [double]$fixture.starter_expected_max_score }
        if ($fixture.PSObject.Properties.Name -contains 'reference_expected_score') { $scoreContractPassed = $scoreContractPassed -and $null -ne $referenceScore -and $referenceScore -eq [double]$fixture.reference_expected_score }
        if ($fixture.PSObject.Properties.Name -contains 'minimum_reference_margin') {
            $comparisonScores = @($starterScore) + @($negativeControlResults | ForEach-Object { $_.score })
            $highestNegative = ($comparisonScores | Measure-Object -Maximum).Maximum
            $scoreContractPassed = $scoreContractPassed -and $null -ne $referenceScore -and ($referenceScore - $highestNegative) -ge [double]$fixture.minimum_reference_margin
        }
        $negativeControlsPassed = @($negativeControlResults | Where-Object { -not $_.passed }).Count -eq 0

        # A bounded timeout is a valid hidden rejection of a deliberately flawed
        # negative control (for example catastrophic regex behavior). Timeouts in
        # public tests or either reference phase remain hard failures.
        $passed = $structureOk -and $starterPublic.exit_code -eq 0 -and $starterHidden.exit_code -ne 0 -and $referencePublic.exit_code -eq 0 -and $referenceHidden.exit_code -eq 0 -and $negativeControlsPassed -and $scoreContractPassed -and $referenceAltPassed
        $diagnostics = @()
        if (-not $passed) {
            $diagnostics = @(
                [pscustomobject]@{phase="starter-public";exit_code=$starterPublic.exit_code;output=$starterPublic.output},
                [pscustomobject]@{phase="starter-hidden";exit_code=$starterHidden.exit_code;output=$starterHidden.output},
                [pscustomobject]@{phase="reference-public";exit_code=$referencePublic.exit_code;output=$referencePublic.output},
                [pscustomobject]@{phase="reference-hidden";exit_code=$referenceHidden.exit_code;output=$referenceHidden.output}
            )
        }
        $results += [pscustomobject]@{
            id = $fixture.id
            structure_complete = $structureOk
            public_starter_passed = ($starterPublic.exit_code -eq 0)
            hidden_rejects_starter = ($starterHidden.exit_code -ne 0)
            public_accepts_reference = ($referencePublic.exit_code -eq 0)
            hidden_accepts_reference = ($referenceHidden.exit_code -eq 0)
            starter_score = $starterScore
            reference_score = $referenceScore
            reference_alt_present = $referenceAltPresent
            reference_alt_score = $referenceAltScore
            reference_alt_passed = $referenceAltPassed
            negative_controls = $negativeControlResults
            score_contract_passed = $scoreContractPassed
            timed_out = (@(@($starterPublic,$starterHidden,$referencePublic,$referenceHidden) | Where-Object { -not $_.completed }).Count -gt 0)
            passed = $passed
            diagnostics = $diagnostics
        }
    } finally {
        if (Test-Path -LiteralPath $temp) { Remove-Item -LiteralPath $temp -Recurse -Force }
    }
}

$failed = @($results | Where-Object { -not $_.passed }).Count
$report = [ordered]@{
    schema_version = 2
    run_at = [datetimeoffset]::Now.ToString("o")
    phase_timeout_seconds = $PhaseTimeoutSeconds
    cases = $results.Count
    passed = $results.Count - $failed
    failed = $failed
    results = $results
}
if (-not $OutputPath) { $OutputPath = Join-Path $root ("Evals/reports/{0}-outcome-harness.json" -f (Get-Date -Format "yyyy-MM-dd-HHmmss")) }
$report | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 -LiteralPath $OutputPath
$report | ConvertTo-Json -Depth 10
if ($failed) { exit 1 }
