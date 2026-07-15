[CmdletBinding()]
param(
    [string]$ObjectivePath = "Objectives/active/OBJ-20260712-agentic-work-best-practices.json",
    [switch]$AllowIncomplete,
    [switch]$Json
)

$ErrorActionPreference = "Stop"
$objective = Get-Content -Raw -Encoding UTF8 -LiteralPath $ObjectivePath | ConvertFrom-Json
$errors = New-Object System.Collections.Generic.List[string]
$warnings = New-Object System.Collections.Generic.List[string]
$seenPillars = @{}
$seenRequirements = @{}
$counts = @{}

foreach ($pillar in $objective.pillars) {
    if ($seenPillars.ContainsKey($pillar.id)) { $errors.Add("Duplicate pillar ID: $($pillar.id)") }
    $seenPillars[$pillar.id] = $true
    foreach ($req in $pillar.requirements) {
        if ($seenRequirements.ContainsKey($req.id)) { $errors.Add("Duplicate requirement ID: $($req.id)") }
        $seenRequirements[$req.id] = $true
        $counts[$req.status] = 1 + [int]($counts[$req.status])

        if (-not $req.acceptance -or $req.acceptance.Count -eq 0) {
            $errors.Add("$($req.id) has no acceptance criteria")
        }
        if ($req.status -eq "verified" -and (-not $req.evidence -or $req.evidence.Count -eq 0)) {
            $errors.Add("$($req.id) is verified without evidence")
        }
        # Evidence must be substantive, not a self-attested placeholder. A verified
        # requirement whose evidence is a bare "done"/"ok"/"passed" or a sub-8-char
        # token is treated as evidence-free.
        if ($req.status -eq "verified" -and $req.evidence -and $req.evidence.Count -gt 0) {
            $placeholder = '^(done|ok|okay|yes|pass|passed|fixed|complete|completed|n/?a|na|true|verified|good)\.?$'
            foreach ($ev in $req.evidence) {
                $trimmed = ([string]$ev).Trim()
                if ($trimmed.Length -lt 8 -or $trimmed -match "(?i)$placeholder") {
                    $errors.Add("$($req.id) is verified with placeholder evidence: '$trimmed'")
                }
            }
        }
        if (($req.status -eq "not_applicable" -or $req.status -eq "rejected") -and [string]::IsNullOrWhiteSpace($req.notes)) {
            $errors.Add("$($req.id) is $($req.status) without a reason")
        }
        if ($req.status -in @("pending", "in_progress", "partial", "blocked")) {
            $warnings.Add("$($req.id) remains $($req.status): $($req.statement)")
        }
    }
}

$complete = $errors.Count -eq 0 -and $warnings.Count -eq 0
$result = [ordered]@{
    objective = $objective.id
    status = $objective.status
    complete = $complete
    pillars = $seenPillars.Count
    requirements = $seenRequirements.Count
    counts = $counts
    errors = @($errors)
    incomplete = @($warnings)
}

if ($Json) {
    $result | ConvertTo-Json -Depth 8
} else {
    Write-Host "Objective: $($objective.id)"
    Write-Host "Coverage: $($seenRequirements.Count) requirements across $($seenPillars.Count) pillars"
    foreach ($key in ($counts.Keys | Sort-Object)) { Write-Host ("  {0}: {1}" -f $key, $counts[$key]) }
    foreach ($e in $errors) { Write-Host "ERROR: $e" -ForegroundColor Red }
    foreach ($w in $warnings) { Write-Host "OPEN:  $w" -ForegroundColor Yellow }
    $label = if ($complete) { "RESULT: PASS" } else { "RESULT: INCOMPLETE" }
    Write-Host $label
}

if ($errors.Count -gt 0) { exit 2 }
if (-not $complete -and -not $AllowIncomplete) { exit 1 }
exit 0
