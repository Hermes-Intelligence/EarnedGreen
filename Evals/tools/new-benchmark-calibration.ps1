[CmdletBinding()]
param(
    [string]$Fixture='database-migration-rollback',
    [ValidateSet('codex','claude')][string]$Provider='codex',
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
$providerConfig=@($settings.providers|Where-Object id -eq $Provider)[0]
if(-not $providerConfig){throw "Provider snapshot missing: $Provider"}
if($providerConfig.model -eq 'provider-default'){throw 'Calibration requires an explicit model selector.'}
$catalog=Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $rootPath 'Evals/fixtures/catalog.json')|ConvertFrom-Json
$fixtureDef=@($catalog.fixtures|Where-Object id -eq $Fixture)[0]
if(-not $fixtureDef){throw "Unknown fixture: $Fixture"}
$task=Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $rootPath (Join-Path $fixtureDef.public_path $fixtureDef.task_file))
$route=& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $rootPath 'tools/route.ps1') -Task $task -Repo (Join-Path $rootPath $fixtureDef.public_path) -NoWrite|ConvertFrom-Json
$requiredModules=@('database-migration','change-impact','security-boundaries')
if($Fixture -eq 'database-migration-rollback' -and @($requiredModules|Where-Object{$_ -notin @($route.selected_modules.id)}).Count){throw 'Calibration fixture no longer routes every expected full-arm module.'}
$runs=@(
    [ordered]@{run_key="calibration::$Fixture::$Provider::vanilla::t1";stage='calibration';fixture=$Fixture;provider=$Provider;arm='vanilla';trial=1;status='pending';run_id=$null},
    [ordered]@{run_key="calibration::$Fixture::$Provider::core-router-enforcement::t1";stage='calibration';fixture=$Fixture;provider=$Provider;arm='core-router-enforcement';trial=1;status='pending';run_id=$null}
)
Get-Random -SetSeed $Seed|Out-Null
$runs=@($runs|Sort-Object{Get-Random})
$harnessFiles=@('Evals/tools/new-run.ps1','Evals/tools/grade-run.ps1','Evals/tools/run-benchmark-stage.ps1','Evals/adapters/providers/invoke-agenticbench.ps1','Evals/fixtures/catalog.json')
$harnessSnapshot=@($harnessFiles|ForEach-Object{[ordered]@{path=$_;sha256=(Get-FileHash -LiteralPath (Join-Path $rootPath $_) -Algorithm SHA256).Hash}})
$id=(Get-Date -Format 'yyyyMMdd-HHmmss')+'-calibration-probe'
$path=Join-Path $OutputRoot $id
New-Item -ItemType Directory -Path $path|Out-Null
$campaign=[ordered]@{
    schema_version=2;campaign_id=$id;campaign_kind='calibration-probe';status='awaiting-calibration-approval';publishable=$false
    created_at=[datetimeoffset]::Now.ToString('o');isolation='dedicated-wsl';provider_snapshot=$settings
    controls=[ordered]@{screening_only=$true;exclude_from_confirmatory_scores=$true;same_prompt_within_fixture=$true;explicit_model_required=$true;clean_workspace_per_run=$true;hidden_graders_host_only=$true;randomized_order=$true;randomization_seed=$Seed;harness_snapshot=$harnessSnapshot;routed_modules=@($route.selected_modules.id)}
    decision_rule=[ordered]@{
        both_scores_100='STOP: ceiling detected; spend zero calls on the second provider and redesign a harder fixture.'
        unequal_scores='CANDIDATE: inspect evidence, then request separate approval for a balanced four-cell confirmatory probe.'
        equal_below_100='STOP: review shared failure mode or grader alignment before spending more.'
        infrastructure_failure='INVALIDATE: retain evidence; replacement requires separate human approval.'
    }
    loop=[ordered]@{objective='Screen one harder fixture for discriminatory signal at minimum subscription cost.';non_goals=@('Publication','Stable promotion','Second-provider execution','Automatic retries');completion='Exactly two approved Codex arms graded or safely stopped.';progress_signal='A pending arm receives a retained disposition.';max_total_runs=2;max_infrastructure_replacements=1;max_runs_per_invocation=2;max_wall_minutes_per_run=15;max_turns_per_run=12;max_consecutive_failures=2;max_no_progress=2;kill_switch='Evals/local/STOP';escalation=@('Any extra-call requirement','Authentication loss','Isolation drift','Provider/model drift')}
    stages=@([ordered]@{id='calibration';expected_new_runs=2;cumulative_runs=2;status='awaiting-approval';approved_at=$null;approved_by=$null})
    runs=$runs
}
$campaign|ConvertTo-Json -Depth 14|Set-Content -Encoding UTF8 -LiteralPath (Join-Path $path 'campaign.json')
[ordered]@{schema_version=1;campaign_id=$id;path=$path;provider=$Provider;model=$providerConfig.model;fixture=$Fixture;calls=2;status=$campaign.status;additional_provider_calls=0}|ConvertTo-Json -Depth 6
