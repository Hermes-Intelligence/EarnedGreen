[CmdletBinding()]
param(
    [Parameter(Position=0, Mandatory=$true)][ValidateSet("preflight", "init", "doctor", "objective-check", "route", "model-recommend", "eval", "research-plan", "promote-candidate", "rollback-release", "handoff-check", "loop-checkpoint")][string]$Command,
    [string]$TargetRepo = (Get-Location).Path,
    [string]$Task,
    [string]$Objective,
    [ValidateSet("anthropic-claude-code", "openai-codex")][string]$Provider,
    [string]$Profile,
    [string]$ExplicitSelector,
    [string]$Candidate,
    [string]$Release,
    [string]$ApprovedBy,
    [string]$HandoffPath,
    [string]$ManifestPath,
    [string]$Action,
    [string]$Fingerprint,
    [string]$Evidence,
    [ValidateSet("core", "benchmark")][string]$Mode = "core",
    [switch]$Approve,
    [switch]$Global,
    [switch]$Json
)

$scripts = @{
    "preflight" = "preflight.ps1"
    "init" = "init.ps1"
    "doctor" = "doctor.ps1"
    "objective-check" = "objective-check.ps1"
    "route" = "route.ps1"
    "model-recommend" = "model-route.ps1"
    "eval" = "../Evals/run-evals.ps1"
    "research-plan" = "../Research/engine/new-candidate.ps1"
    "promote-candidate" = "promote-candidate.ps1"
    "rollback-release" = "rollback-release.ps1"
    "handoff-check" = "handoff-check.ps1"
    "loop-checkpoint" = "loop-checkpoint.ps1"
}
$script = Join-Path $PSScriptRoot $scripts[$Command]
switch ($Command) {
    "preflight" { & $script -Mode $Mode -TargetRepo $TargetRepo -Json:$Json }
    "init" { & $script -TargetRepo $TargetRepo -Global:$Global }
    "doctor" { & $script -TargetRepo $TargetRepo -Json:$Json }
    "objective-check" { & $script -ObjectivePath $(if ($Objective) { $Objective } else { "Objectives/active/OBJ-20260712-agentic-work-best-practices.json" }) -Json:$Json }
    "route" { if (-not $Task) { throw "-Task is required for route" }; & $script -Task $Task -Repo $TargetRepo }
    "model-recommend" { if (-not $Provider -or -not $Profile) { throw "-Provider and -Profile are required for model-recommend" }; & $script -Provider $Provider -Profile $Profile -ExplicitSelector $ExplicitSelector }
    "eval" { & $script }
    "research-plan" { & $script }
    "promote-candidate" { if(-not $Candidate){throw '-Candidate is required'}; & $script -Candidate $Candidate -Approve:$Approve -ApprovedBy $ApprovedBy }
    "rollback-release" { if(-not $Release){throw '-Release is required'}; & $script -Release $Release -Approve:$Approve -ApprovedBy $ApprovedBy }
    "handoff-check" { if(-not $HandoffPath){throw '-HandoffPath is required'}; & $script -HandoffPath $HandoffPath }
    "loop-checkpoint" { if(-not $ManifestPath -or -not $Action){throw '-ManifestPath and -Action are required'}; & $script -ManifestPath $ManifestPath -Action $Action -Fingerprint $Fingerprint -Evidence $Evidence }
}
exit $LASTEXITCODE
