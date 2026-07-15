[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$Experiment,[string]$Root)
$ErrorActionPreference='Stop';if(-not $Root){$Root=Split-Path -Parent (Split-Path -Parent $PSScriptRoot)};$rootPath=(Resolve-Path $Root).Path;$expPath=if([IO.Path]::IsPathRooted($Experiment)){(Resolve-Path $Experiment).Path}else{(Resolve-Path (Join-Path $rootPath "Evals/experiments/$Experiment")).Path};$plan=Get-Content -Raw (Join-Path $expPath 'plan.json')|ConvertFrom-Json
# Load one record per PLANNED run, keyed by run_id. A planned run whose record
# file is missing or unparseable is kept as $null so it is counted as a failed
# trial in the denominator below (rather than silently dropped, which inflates
# pass rates).
$recordByRun=@{};foreach($run in $plan.runs){if($run.run_id){$recordPath=Join-Path $rootPath "Evals/runs/$($run.run_id)/run-record.json";$rec=$null;if(Test-Path $recordPath){try{$rec=Get-Content -Raw -Encoding UTF8 $recordPath|ConvertFrom-Json}catch{$rec=$null}};$recordByRun[[string]$run.run_id]=$rec}}
$records=@($recordByRun.Values|Where-Object{$_ -ne $null})
function Test-RecordValid($rec){return $rec -and ($rec.PSObject.Properties.Name -contains 'outcome_valid') -and [bool]$rec.outcome_valid -and $rec.grader}
function Wilson([int]$success,[int]$n){if($n -eq 0){return @($null,$null)};$z=1.96;$p=$success/$n;$den=1+$z*$z/$n;$center=($p+$z*$z/(2*$n))/$den;$margin=$z*[math]::Sqrt(($p*(1-$p)+$z*$z/(4*$n))/$n)/$den;return @([math]::Round($center-$margin,4),[math]::Round($center+$margin,4))}
$missingOrInvalidTotal=0
$cells=@();foreach($f in @($plan.runs.fixture|Sort-Object -Unique)){foreach($a in @($plan.runs.arm|Sort-Object -Unique)){
    $planned=@($plan.runs|Where-Object{$_.fixture -eq $f -and $_.arm -eq $a})
    if($planned.Count -eq 0){continue}
    $n=$planned.Count;$success=0;$invalid=0;$scoreList=@();$validRecords=@()
    foreach($pr in $planned){
        $rec=$recordByRun[[string]$pr.run_id]
        if(-not (Test-RecordValid $rec)){$invalid++;$scoreList+=0.0;continue}
        $validRecords+=$rec;$scoreList+=[double]$rec.grader.score
        if($rec.grader.passed -and $rec.public_tests.passed -and $rec.enforcement_passed){$success++}
    }
    $missingOrInvalidTotal+=$invalid
    $ci=Wilson $success $n
    $mean=($scoreList|Measure-Object -Average).Average
    $validTrials=$n-$invalid
    $cells+=[ordered]@{fixture=$f;arm=$a;n=$n;valid_trials=$validTrials;invalid_or_missing=$invalid;success=$success;pass_rate=if($n){[math]::Round($success/$n,4)}else{$null};wilson95_low=$ci[0];wilson95_high=$ci[1];mean_score=[math]::Round($mean,2);total_cost=[math]::Round((($validRecords|Measure-Object cost -Sum).Sum),4);total_tokens=(($validRecords|Measure-Object tokens -Sum).Sum);complete=($validTrials -ge $plan.controls.minimum_trials_per_cell)}
}}
$complete=@($cells|Where-Object{-not $_.complete}).Count -eq 0;$publishable=$complete -and $missingOrInvalidTotal -eq 0 -and $plan.publishable_hidden_results -and $plan.budget.approved
$summary=[ordered]@{schema_version=1;experiment_id=$plan.experiment_id;generated_at=[datetimeoffset]::Now.ToString('o');records=$records.Count;planned_runs=@($plan.runs).Count;missing_or_invalid_records=$missingOrInvalidTotal;cells=$cells;complete=$complete;publishable=$publishable;publication_blockers=@($(if(-not $complete){'fewer than the required number of valid trials in one or more cells'}),$(if($missingOrInvalidTotal -gt 0){"$missingOrInvalidTotal planned run(s) have a missing or invalid run-record"}),$(if(-not $plan.publishable_hidden_results){'hidden grader isolation is logical-only'}),$(if(-not $plan.budget.approved){'budget was not approved'}))|Where-Object{$_}}
$summary|ConvertTo-Json -Depth 10|Set-Content -Encoding UTF8 (Join-Path $expPath 'summary.json');$summary|ConvertTo-Json -Depth 10;if(-not $complete){exit 2}
