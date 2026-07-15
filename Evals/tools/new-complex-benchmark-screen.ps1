[CmdletBinding()]
param(
    [int]$Seed=20260713,
    [string]$ProviderSettings,
    [string]$OutputRoot,
    [string]$Root
)
$ErrorActionPreference='Stop'
if(-not $Root){$Root=Split-Path -Parent (Split-Path -Parent $PSScriptRoot)}
$rootPath=(Resolve-Path -LiteralPath $Root).Path
if(-not $ProviderSettings){$ProviderSettings=Join-Path $rootPath 'Evals/local/provider-settings.json'}
if(-not $OutputRoot){$OutputRoot=Join-Path $rootPath 'Evals/experiments'}
$settings=Get-Content -Raw -Encoding UTF8 -LiteralPath $ProviderSettings|ConvertFrom-Json
if([datetimeoffset]$settings.expires_at -le [datetimeoffset]::Now){throw 'Local provider settings expired.'}
$provider=@($settings.providers|Where-Object id -eq 'codex')[0]
if(-not $provider -or $provider.model -eq 'provider-default'){throw 'Complex screen requires an explicit Codex model selector.'}
$catalog=Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $rootPath 'Evals/fixtures/catalog.json')|ConvertFrom-Json
$fixture=@($catalog.fixtures|Where-Object id -eq 'production-ingestion-evolution')[0]
if(-not $fixture -or @($fixture.negative_controls).Count -lt 3){throw 'Composite fixture or its negative-control ladder is incomplete.'}
$protocol=Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $rootPath 'Evals/baselines/production-ingestion-protocol.json')|ConvertFrom-Json
if($protocol.zero_provider_discrimination.reference -ne 100 -or $protocol.zero_provider_discrimination.reference_margin_over_strongest_negative -lt 15){throw 'Composite discrimination evidence is below the approved design floor.'}
# Fixture admission (pre-spend) and canary rule.
. (Join-Path $PSScriptRoot 'fixture-admission.ps1')
Assert-FixtureAdmission -RootPath $rootPath -FixtureIds @('production-ingestion-evolution') -Context 'complex screen creation (pre-spend)'
$canaryFixtures=Get-CanaryFixtures -RootPath $rootPath -FixtureIds @('production-ingestion-evolution')
$runs=@()
foreach($trial in 1..3){
    foreach($arm in @('vanilla','core-router-enforcement')){
        $runs+=[ordered]@{run_key="complex-screen::production-ingestion-evolution::codex::$arm::t$trial";stage='complex-screen';fixture='production-ingestion-evolution';provider='codex';arm=$arm;trial=$trial;grader_seed=20260713+$trial;canary=('production-ingestion-evolution' -in $canaryFixtures);status='pending';run_id=$null}
    }
}
Get-Random -SetSeed $Seed|Out-Null;$runs=@($runs|Sort-Object{Get-Random})
$harnessFiles=@('Evals/tools/new-run.ps1','Evals/tools/grade-run.ps1','Evals/tools/run-benchmark-stage.ps1','Evals/adapters/providers/invoke-agenticbench.ps1','Evals/tools/read-provider-telemetry.ps1','Evals/fixtures/catalog.json','Evals/fixtures/production-ingestion-evolution/hidden/grade.py','Evals/baselines/production-ingestion-protocol.json')
$harnessSnapshot=@($harnessFiles|ForEach-Object{[ordered]@{path=$_;sha256=(Get-FileHash -LiteralPath (Join-Path $rootPath $_) -Algorithm SHA256).Hash}})
$id=(Get-Date -Format 'yyyyMMdd-HHmmss')+'-complex-ingestion-screen'
$path=Join-Path $OutputRoot $id;New-Item -ItemType Directory -Path $path|Out-Null
$campaign=[ordered]@{
    schema_version=2;campaign_id=$id;campaign_kind='complex-quality-screen';status='awaiting-complex-screen-approval';publishable=$false;created_at=[datetimeoffset]::Now.ToString('o');isolation='dedicated-wsl';provider_snapshot=$settings
    canary_policy=(New-CanaryPolicy -CanaryFixtures $canaryFixtures)
    controls=[ordered]@{screening_only=$true;exclude_from_confirmatory_scores=$true;explicit_model_required=$true;paired_trial_seeds=$true;same_prompt_within_fixture=$true;clean_workspace_per_run=$true;hidden_graders_host_only=$true;randomized_order=$true;randomization_seed=$Seed;harness_snapshot=$harnessSnapshot;quality_dimensions=$protocol.primary_outcomes.hidden_quality_score.dimensions;smallest_meaningful_difference=$protocol.primary_outcomes.hidden_quality_score.smallest_meaningful_difference}
    decision_rule=[ordered]@{repeated_ceiling='STOP if both arms score 100 in every pair.';no_actionable_signal='STOP if every paired difference is within 3 points and no critical check differs.';material_signal='Only an 8-point paired quality difference or critical-floor difference may be proposed for a separately approved confirmation.';infrastructure_failure='INVALIDATE and retain evidence; replacements require separate approval.'}
    loop=[ordered]@{objective='Screen a composite production task for agentic-environment quality lift while measuring time, tokens and provider-reported cost.';non_goals=@('Publication','Stable promotion','Claude execution','Automatic confirmation','Automatic retries');completion='Exactly six approved Codex outcomes are scored or the loop stops safely.';progress_signal='A pending arm receives a retained passed, scored or invalid disposition.';max_total_runs=6;max_infrastructure_replacements=0;max_runs_per_invocation=6;max_wall_minutes_per_run=20;max_turns_per_run=16;max_consecutive_failures=2;max_no_progress=2;kill_switch='Evals/local/STOP';escalation=@('Any extra-call requirement','Authentication loss','Isolation drift','Provider/model drift','Harness hash drift')}
    stages=@([ordered]@{id='complex-screen';expected_new_runs=6;cumulative_runs=6;status='awaiting-approval';approved_at=$null;approved_by=$null})
    runs=$runs
}
$campaign|ConvertTo-Json -Depth 14|Set-Content -Encoding UTF8 -LiteralPath (Join-Path $path 'campaign.json')
[ordered]@{schema_version=1;campaign_id=$id;path=$path;provider='codex';model=$provider.model;fixture='production-ingestion-evolution';calls=6;trials_per_arm=3;status=$campaign.status;additional_provider_calls=0}|ConvertTo-Json -Depth 6
