[CmdletBinding()]
param(
    [string[]]$Fixtures=@('entity-parser-unseen','objective-omission'),
    [string[]]$Arms=@('vanilla','core','core-router','core-router-enforcement'),
    [int]$Trials=5,
    [Parameter(Mandatory=$true)][string]$Provider,
    [string]$ModelProfile='balanced-daily',
    [ValidateSet('logical-only','container','vm')][string]$Isolation='logical-only',
    [double]$MaxTotalCost=0,
    [double]$MaxWallHours=8,
    [int]$Seed=20260712,
    [switch]$ApproveBudget,
    [string]$ApprovedBy,
    [string]$Root
)
$ErrorActionPreference='Stop';if(-not $Root){$Root=Split-Path -Parent (Split-Path -Parent $PSScriptRoot)};$rootPath=(Resolve-Path $Root).Path
if($Trials -lt 5){throw 'At least five trials per fixture/arm cell are required.'};if($ApproveBudget -and -not $ApprovedBy){throw '-ApprovedBy is required with -ApproveBudget.'}
$catalog=Get-Content -Raw (Join-Path $rootPath 'Evals/fixtures/catalog.json')|ConvertFrom-Json;$known=@($catalog.fixtures.id);foreach($f in $Fixtures){if($f -notin $known){throw "Fixture is not executable: $f"}}
$validArms=@('vanilla','core','core-router','core-router-enforcement');foreach($a in $Arms){if($a -notin $validArms){throw "Unknown arm: $a"}}
$id=(Get-Date -Format 'yyyyMMdd-HHmmss')+'-pilot';$path=Join-Path $rootPath "Evals/experiments/$id";New-Item -ItemType Directory -Path $path|Out-Null;$runs=@();foreach($f in $Fixtures){foreach($a in $Arms){1..$Trials|ForEach-Object{$runs+=[ordered]@{run_key="$f::$a::t$_";fixture=$f;arm=$a;trial=$_;status='pending';run_id=$null}}}};Get-Random -SetSeed $Seed|Out-Null
$plan=[ordered]@{schema_version=1;experiment_id=$id;status=if($ApproveBudget){'approved'}else{'awaiting-budget-approval'};created_at=[datetimeoffset]::Now.ToString('o');provider=$Provider;model_profile=$ModelProfile;isolation=$Isolation;publishable_hidden_results=($Isolation -in @('container','vm'));controls=[ordered]@{same_model_version=$true;same_reasoning_effort=$true;same_task_prompt=$true;same_clean_fixture=$true;same_time_and_cost_budget=$true;minimum_trials_per_cell=5;randomize_run_order=$true;randomization_seed=$Seed;hidden_graders_unavailable_to_agent=($Isolation -in @('container','vm'))};budget=[ordered]@{max_total_cost=$MaxTotalCost;max_wall_hours=$MaxWallHours;approved=[bool]$ApproveBudget;approved_by=if($ApproveBudget){$ApprovedBy}else{$null};kill_on_budget=$true};runs=@($runs|Sort-Object{Get-Random})}
$plan|ConvertTo-Json -Depth 10|Set-Content -Encoding UTF8 (Join-Path $path 'plan.json');[ordered]@{experiment_id=$id;path=$path;status=$plan.status;runs=$runs.Count;publishable_hidden_results=$plan.publishable_hidden_results}|ConvertTo-Json
