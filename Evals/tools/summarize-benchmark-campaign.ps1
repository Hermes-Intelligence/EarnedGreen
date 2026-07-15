[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Campaign,
    [Parameter(Mandatory=$true)][ValidateSet('calibration','complex-screen','smoke','directional','confidence','pilot')][string]$Stage,
    [string[]]$ReviewNote=@(),
    [string]$Root
)
$ErrorActionPreference='Stop'
if(-not $Root){$Root=Split-Path -Parent (Split-Path -Parent $PSScriptRoot)}
$rootPath=(Resolve-Path -LiteralPath $Root).Path
$experimentsRoot=(Resolve-Path -LiteralPath (Join-Path $rootPath 'Evals/experiments')).Path
$campaignDir=if([IO.Path]::IsPathRooted($Campaign)){(Resolve-Path -LiteralPath $Campaign).Path}else{(Resolve-Path -LiteralPath (Join-Path $experimentsRoot $Campaign)).Path}
if(-not $campaignDir.StartsWith($experimentsRoot+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'Campaign escaped Evals/experiments.'}
$data=Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $campaignDir 'campaign.json')|ConvertFrom-Json
$stageData=@($data.stages|Where-Object id -eq $Stage)[0]
if($stageData.status -ne 'complete'){throw "Stage '$Stage' is not complete."}
$entries=@($data.runs|Where-Object stage -eq $Stage)
$rows=@()
foreach($entry in $entries){
    if(-not $entry.run_id){throw "Run id missing for $($entry.run_key)."}
    $runDir=Join-Path $rootPath "Evals/runs/$($entry.run_id)"
    $execution=Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $runDir 'provider-execution.json')|ConvertFrom-Json
    $record=Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $runDir 'run-record.json')|ConvertFrom-Json
    $model=([string]$execution.actual_model -replace '\[[0-9;]*m\]?','').Trim()
    $rows+=[pscustomobject][ordered]@{
        provider=$entry.provider;arm=$entry.arm;fixture=$entry.fixture;trial=$entry.trial;status=$entry.status;run_id=$entry.run_id
        started_at=$execution.started_at;finished_at=$execution.finished_at;duration_seconds=[math]::Round((([datetimeoffset]$execution.finished_at)-([datetimeoffset]$execution.started_at)).TotalSeconds,1)
        actual_model=$model;model_evidence=$execution.model_evidence;provider_exit=[int]$execution.exit_code;copied_back=[bool]$execution.copied_back
        total_observed_tokens=if($execution.token_usage){[long]$execution.token_usage.total_observed_tokens}else{[long]$record.tokens}
        token_usage=if($execution.token_usage){$execution.token_usage}else{$record.token_usage}
        reported_cost_usd=if($execution.monetary_cost -and $null -ne $execution.monetary_cost.amount_usd){[double]$execution.monetary_cost.amount_usd}else{$null}
        cost_basis=if($execution.monetary_cost){[string]$execution.monetary_cost.basis}else{'not-recorded'}
        public_pass=[bool]$record.public_tests.passed;hidden_pass=[bool]$record.grader.passed;hidden_score=[double]$record.grader.score
        enforcement_pass=[bool]$record.enforcement_passed;changed_files=@($record.changed_files);protected_files_changed=@($record.protected_files_changed)
    }
}
$ordered=@($rows|Sort-Object{[datetimeoffset]$_.started_at});$overlaps=@()
for($i=1;$i -lt $ordered.Count;$i++){if([datetimeoffset]$ordered[$i].started_at -lt [datetimeoffset]$ordered[$i-1].finished_at){$overlaps+=[ordered]@{first=$ordered[$i-1].run_id;second=$ordered[$i].run_id}}}
$invalid=@($data.invalid_attempts|Where-Object{$_})
$allPassed=@($rows|Where-Object{-not($_.status -eq 'passed' -and $_.provider_exit -eq 0 -and $_.public_pass -and $_.hidden_pass -and $_.hidden_score -eq 100 -and $_.enforcement_pass)}).Count -eq 0
$fullIntegrity=@($rows|Where-Object{$_.arm -eq 'core-router-enforcement' -and @($_.protected_files_changed).Count -gt 0}).Count -eq 0
$unresolved=@($rows|Where-Object actual_model -eq 'unresolved-provider-default')
$isCalibration=$Stage -eq 'calibration'
$scores=@($rows|ForEach-Object{[double]$_.hidden_score})
$calibrationConclusion=if(-not $isCalibration){'INCONCLUSIVE'}elseif($rows.Count -eq 2 -and @($scores|Where-Object{$_ -eq 100}).Count -eq 2){'CEILING'}elseif($rows.Count -eq 2 -and $scores[0] -ne $scores[1]){'SIGNAL'}elseif($rows.Count -eq 2){'SHARED_FAILURE'}else{'INVALID'}
$blockers=if($isCalibration){@('Screening-only calibration is excluded from publishable confirmatory scores.')}else{@('Only one trial per provider/arm cell; comparative effect is statistically inconclusive.')}
if($unresolved.Count){$blockers+='Codex provider-default did not report an exact resolved model; post-smoke stages require explicit model selectors.'}
if($invalid.Count){$blockers+='One or more infrastructure-invalid attempts exist.'}
$nextGate=if($isCalibration){
    switch($calibrationConclusion){
        'CEILING' {'STOP: both arms scored 100. Spend zero Claude calls and redesign a harder fixture before requesting any new provider approval.'}
        'SIGNAL' {'Inspect the exact score/evidence difference. Any balanced four-cell confirmation requires a new campaign and separate human approval.'}
        'SHARED_FAILURE' {'STOP: inspect the shared failure mode or grader alignment before spending more.'}
        default {'STOP: calibration evidence is invalid or incomplete; retain it and request separate approval before any replacement.'}
    }
}else{'Directional remains unapproved. Create a new campaign with explicit model selectors before any post-smoke calls, then require separate human approval.'}
$summary=[ordered]@{
    schema_version=1;campaign_id=$data.campaign_id;stage=$Stage;generated_at=[datetimeoffset]::Now.ToString('o')
    verdict=if($allPassed -and -not $overlaps.Count -and -not $invalid.Count){'PASS'}else{'FAIL'}
    comparative_conclusion=$calibrationConclusion;publishable_comparison=$false
    scheduled_calls=$entries.Count;completed_calls=@($rows|Where-Object status -in @('passed','scored')).Count;invalid_attempts=$invalid.Count;overlap_count=$overlaps.Count
    all_public_hidden_100=$allPassed;full_arm_integrity_passed=$fullIntegrity;total_provider_seconds=[math]::Round((($rows|Measure-Object duration_seconds -Sum).Sum),1)
    total_observed_tokens=[long](($rows|Measure-Object total_observed_tokens -Sum).Sum)
    total_reported_cost_usd=if(@($rows|Where-Object{$null -ne $_.reported_cost_usd}).Count){[math]::Round((($rows|Where-Object{$null -ne $_.reported_cost_usd}|Measure-Object reported_cost_usd -Sum).Sum),6)}else{$null}
    monetary_cost_coverage="$(@($rows|Where-Object{$null -ne $_.reported_cost_usd}).Count)/$($rows.Count) provider calls"
    provider_snapshot=$data.provider_snapshot;harness_snapshot=$data.controls.harness_snapshot;runs=$rows;overlaps=$overlaps
    review_notes=@($ReviewNote);publication_blockers=$blockers
    decision_rule=$data.decision_rule;next_gate=$nextGate
}
$base=Join-Path $rootPath "Evals/reports/$($data.campaign_id)-$Stage"
$summary|ConvertTo-Json -Depth 12|Set-Content -Encoding UTF8 -LiteralPath ($base+'.json')
$title=if($isCalibration){'# Calibration Benchmark Report'}else{'# Smoke Benchmark Report'}
$executive=if($isCalibration){
    "All $($summary.completed_calls)/$($summary.scheduled_calls) approved calls passed public tests, hidden grading at 100/100 and applicable enforcement. There were $($summary.overlap_count) overlapping executions and $($summary.invalid_attempts) invalid attempts. Both arms reached the ceiling, so this fixture cannot discriminate between vanilla and the full environment. The predeclared decision is STOP: spend zero Claude calls and redesign a harder fixture."
}else{
    "All $($summary.completed_calls)/$($summary.scheduled_calls) approved calls passed public tests, hidden grading at 100/100 and applicable enforcement. There were $($summary.overlap_count) overlapping executions and $($summary.invalid_attempts) invalid attempts. This proves smoke viability of the repaired harness; it does not prove that the full arm outperforms vanilla."
}
$md=@(
    $title,'',
    "- Campaign: ``$($data.campaign_id)``","- Generated: $($summary.generated_at)","- Verdict: **$($summary.verdict)**","- Comparative conclusion: **$($summary.comparative_conclusion)**",'',
    '## Executive result','',
    $executive,'',
    '## Run evidence','',
    '| Provider | Arm | Model evidence | Seconds | Public | Hidden | Enforcement | Protected changes |','|---|---|---|---:|---|---:|---|---:|'
)
foreach($row in $rows){$md+="| $($row.provider) | $($row.arm) | $($row.actual_model) ($($row.model_evidence)) | $($row.duration_seconds) | $($row.public_pass) | $($row.hidden_score) | $($row.enforcement_pass) | $(@($row.protected_files_changed).Count) |"}
$md+=@('','## Integrity and review','',"- Harness snapshot: $(@($summary.harness_snapshot).Count) pinned file hashes.","- Full-arm protected-input integrity: $($summary.full_arm_integrity_passed).","- Total provider wall time: $($summary.total_provider_seconds) seconds.")
foreach($note in $summary.review_notes){$md+="- $note"}
$md+="- Total observed tokens: $($summary.total_observed_tokens)."
$md+="- Reported monetary-cost coverage: $($summary.monetary_cost_coverage); subscription charges may differ."
$md+=@('','## Publication blockers','')
foreach($blocker in $summary.publication_blockers){$md+="- $blocker"}
$md+=@('','## Next gate','',$summary.next_gate,'','Structured JSON beside this report is the measurement source of truth. The PDF is a human-readable artifact.')
$md -join [Environment]::NewLine|Set-Content -Encoding UTF8 -LiteralPath ($base+'.md')
[ordered]@{schema_version=1;json=$base+'.json';markdown=$base+'.md';verdict=$summary.verdict;comparative_conclusion=$summary.comparative_conclusion;provider_calls=$summary.completed_calls;additional_provider_calls=0}|ConvertTo-Json -Depth 6
