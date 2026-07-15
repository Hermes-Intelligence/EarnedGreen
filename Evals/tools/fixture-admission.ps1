# Fixture admission and canary helper library. Dot-source this file; it defines
# functions only and never executes side effects on load.
#
# Fixture admission (pre-spend): a catalog fixture may enter a paid campaign or
# an approved stage only when a fresh validity record exists - an
# Evals/reports/*-outcome-harness.json entry for that fixture with passed=true
# whose run_at is newer than the newest file write under the fixture directory.
#
# Canary rule: a fixture with zero prior paid runs whose run-record shows
# outcome_valid=true is a canary. Its first stage executes at most one run, and
# later stages are refused until a canary run-record exists with
# outcome_valid=true and at least two distinct grader check dimensions.

function Get-FixtureAdmissionCatalog {
    param([Parameter(Mandatory = $true)][string]$RootPath)
    $catalogPath = Join-Path $RootPath 'Evals/fixtures/catalog.json'
    if (-not (Test-Path -LiteralPath $catalogPath)) { throw "Fixture catalog not found: $catalogPath" }
    Get-Content -Raw -Encoding UTF8 -LiteralPath $catalogPath | ConvertFrom-Json
}

function Get-FixtureNewestWriteTime {
    param(
        [Parameter(Mandatory = $true)][string]$RootPath,
        [Parameter(Mandatory = $true)]$CatalogEntry
    )
    $fixtureDir = Join-Path $RootPath (Split-Path -Parent ([string]$CatalogEntry.public_path))
    if (-not (Test-Path -LiteralPath $fixtureDir)) { throw "Fixture directory missing: $fixtureDir" }
    $files = @(Get-ChildItem -LiteralPath $fixtureDir -Recurse -File)
    if (-not $files.Count) { throw "Fixture directory contains no files: $fixtureDir" }
    [datetimeoffset](($files | Measure-Object -Property LastWriteTime -Maximum).Maximum)
}

function Get-FreshFixtureValidityRecord {
    param(
        [Parameter(Mandatory = $true)][string]$RootPath,
        [Parameter(Mandatory = $true)][string]$FixtureId,
        $Catalog
    )
    if (-not $Catalog) { $Catalog = Get-FixtureAdmissionCatalog -RootPath $RootPath }
    $entry = @($Catalog.fixtures | Where-Object { $_.id -eq $FixtureId })
    if ($entry.Count -ne 1) { return $null }
    $newestWrite = Get-FixtureNewestWriteTime -RootPath $RootPath -CatalogEntry $entry[0]
    $reportsDir = Join-Path $RootPath 'Evals/reports'
    if (-not (Test-Path -LiteralPath $reportsDir)) { return $null }
    $reportFiles = @(Get-ChildItem -LiteralPath $reportsDir -Filter '*outcome-harness*.json' -File | Sort-Object LastWriteTime -Descending)
    foreach ($file in $reportFiles) {
        $report = $null
        try { $report = Get-Content -Raw -Encoding UTF8 -LiteralPath $file.FullName | ConvertFrom-Json } catch { continue }
        if (-not $report -or -not ($report.PSObject.Properties.Name -contains 'run_at')) { continue }
        $runAt = $null
        try { $runAt = [datetimeoffset]$report.run_at } catch { continue }
        if ($runAt -le $newestWrite) { continue }
        $hit = @($report.results | Where-Object { $_.id -eq $FixtureId -and [bool]$_.passed })
        if ($hit.Count -ge 1) {
            return [pscustomobject]@{
                fixture = $FixtureId
                report = $file.FullName
                run_at = $runAt.ToString('o')
                fixture_newest_write = $newestWrite.ToString('o')
            }
        }
    }
    return $null
}

function Assert-FixtureAdmission {
    param(
        [Parameter(Mandatory = $true)][string]$RootPath,
        [Parameter(Mandatory = $true)][string[]]$FixtureIds,
        [string]$Context = 'paid execution'
    )
    $catalog = Get-FixtureAdmissionCatalog -RootPath $RootPath
    foreach ($fixtureId in @($FixtureIds | Sort-Object -Unique)) {
        $entry = @($catalog.fixtures | Where-Object { $_.id -eq $fixtureId })
        if ($entry.Count -ne 1) {
            throw "Fixture admission failed for '$fixtureId' ($Context): the fixture is not a catalog fixture in Evals/fixtures/catalog.json, so no validity record can admit it. Add it to the catalog and validate it before any paid run."
        }
        $record = Get-FreshFixtureValidityRecord -RootPath $RootPath -FixtureId $fixtureId -Catalog $catalog
        if (-not $record) {
            throw ("Fixture admission failed for '{0}' ({1}): no fresh validity record. Required: an Evals/reports/*-outcome-harness.json result for this fixture with passed=true and run_at newer than the fixture's newest file write. Produce it with: powershell -ExecutionPolicy Bypass -File Evals/validate-outcome-harness.ps1 -Fixture {0}" -f $fixtureId, $Context)
        }
    }
}

function Get-FixturePaidValidRunCount {
    param(
        [Parameter(Mandatory = $true)][string]$RootPath,
        [Parameter(Mandatory = $true)][string]$FixtureId
    )
    $count = 0
    $runsRoot = Join-Path $RootPath 'Evals/runs'
    if (-not (Test-Path -LiteralPath $runsRoot)) { return $count }
    foreach ($dir in @(Get-ChildItem -LiteralPath $runsRoot -Directory)) {
        $recordPath = Join-Path $dir.FullName 'run-record.json'
        if (-not (Test-Path -LiteralPath $recordPath)) { continue }
        $record = $null
        try { $record = Get-Content -Raw -Encoding UTF8 -LiteralPath $recordPath | ConvertFrom-Json } catch { continue }
        if (-not $record) { continue }
        $names = @($record.PSObject.Properties.Name)
        if ($names -notcontains 'case_id' -or [string]$record.case_id -ne $FixtureId) { continue }
        $provider = if ($names -contains 'provider') { [string]$record.provider } else { '' }
        if ($provider -notmatch '^(codex|claude)') { continue }
        if ($names -contains 'outcome_valid' -and [bool]$record.outcome_valid) { $count++ }
    }
    return $count
}

function Get-RunRecordDistinctDimensionCount {
    param([Parameter(Mandatory = $true)]$Record)
    if (-not ($Record.PSObject.Properties.Name -contains 'grader') -or -not $Record.grader) { return 0 }
    $grader = $Record.grader
    $dimensions = @()
    if (($grader.PSObject.Properties.Name -contains 'checks') -and $grader.checks) {
        $dimensions = @($grader.checks | ForEach-Object {
            if ($_.PSObject.Properties.Name -contains 'dimension') { [string]$_.dimension }
        } | Where-Object { $_ } | Sort-Object -Unique)
    }
    if (-not $dimensions.Count -and ($grader.PSObject.Properties.Name -contains 'dimensions') -and $grader.dimensions) {
        $dimensions = @($grader.dimensions.PSObject.Properties.Name)
    }
    return $dimensions.Count
}

function Test-CanaryRunRecordValid {
    param([Parameter(Mandatory = $true)]$Record)
    $names = @($Record.PSObject.Properties.Name)
    if ($names -notcontains 'outcome_valid' -or -not [bool]$Record.outcome_valid) { return $false }
    return ((Get-RunRecordDistinctDimensionCount -Record $Record) -ge 2)
}

function Test-CanaryRecordSatisfied {
    param(
        [Parameter(Mandatory = $true)][string]$RootPath,
        [Parameter(Mandatory = $true)]$Campaign,
        [Parameter(Mandatory = $true)][string]$FixtureId
    )
    # Campaign-scoped canary run records first.
    foreach ($run in @($Campaign.runs | Where-Object { $_.fixture -eq $FixtureId -and $_.run_id })) {
        $recordPath = Join-Path $RootPath ("Evals/runs/{0}/run-record.json" -f [string]$run.run_id)
        if (-not (Test-Path -LiteralPath $recordPath)) { continue }
        $record = $null
        try { $record = Get-Content -Raw -Encoding UTF8 -LiteralPath $recordPath | ConvertFrom-Json } catch { continue }
        if ($record -and (Test-CanaryRunRecordValid -Record $record)) { return $true }
    }
    # Any other paid validated multi-dimension record also satisfies the rule
    # (the fixture is then no longer zero-history).
    $runsRoot = Join-Path $RootPath 'Evals/runs'
    if (Test-Path -LiteralPath $runsRoot) {
        foreach ($dir in @(Get-ChildItem -LiteralPath $runsRoot -Directory)) {
            $recordPath = Join-Path $dir.FullName 'run-record.json'
            if (-not (Test-Path -LiteralPath $recordPath)) { continue }
            $record = $null
            try { $record = Get-Content -Raw -Encoding UTF8 -LiteralPath $recordPath | ConvertFrom-Json } catch { continue }
            if (-not $record) { continue }
            $names = @($record.PSObject.Properties.Name)
            if ($names -notcontains 'case_id' -or [string]$record.case_id -ne $FixtureId) { continue }
            $provider = if ($names -contains 'provider') { [string]$record.provider } else { '' }
            if ($provider -notmatch '^(codex|claude)') { continue }
            if (Test-CanaryRunRecordValid -Record $record) { return $true }
        }
    }
    return $false
}

function Get-CanaryFixtures {
    param(
        [Parameter(Mandatory = $true)][string]$RootPath,
        [Parameter(Mandatory = $true)][string[]]$FixtureIds
    )
    return @(@($FixtureIds | Sort-Object -Unique) | Where-Object {
        (Get-FixturePaidValidRunCount -RootPath $RootPath -FixtureId $_) -eq 0
    })
}

function New-CanaryPolicy {
    param([string[]]$CanaryFixtures = @())
    return [ordered]@{
        canary_fixtures = @($CanaryFixtures)
        stage1_cap_per_fixture = 1
        stage2_entry = 'A canary fixture may run beyond its first stage only after a canary run-record exists with outcome_valid=true and at least 2 distinct grader check dimensions.'
    }
}
