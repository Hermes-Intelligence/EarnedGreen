[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$Run, [Parameter(Mandatory=$true)][string]$ActualModel, [Parameter(Mandatory=$true)][string]$Effort, [double]$Cost=0, [int]$Tokens=0, [string]$Root)
$ErrorActionPreference="Stop"
function Get-LastJson([string]$text){
    # Scan grader stdout/stderr from last line to first and return the first line
    # that parses as JSON. A grader that emits a Python traceback (agent left a
    # syntax/import/runtime error) no longer kills this script; we return $null
    # and the caller records the failure instead of dropping the run.
    if([string]::IsNullOrWhiteSpace($text)){return $null}
    $lines=@($text.Trim() -split "\r?\n")
    for($i=$lines.Count-1;$i -ge 0;$i--){
        $line=$lines[$i].Trim()
        if($line.Length -eq 0){continue}
        try{ return ($line | ConvertFrom-Json) }catch{}
    }
    return $null
}
if(-not $Root){$Root=Split-Path -Parent (Split-Path -Parent $PSScriptRoot)}
$rootPath=(Resolve-Path $Root).Path;$runPath=if([IO.Path]::IsPathRooted($Run)){(Resolve-Path $Run).Path}else{(Resolve-Path (Join-Path $rootPath "Evals/runs/$Run")).Path}
if(-not $runPath.StartsWith((Resolve-Path (Join-Path $rootPath 'Evals/runs')).Path+[IO.Path]::DirectorySeparatorChar)){throw 'Run escaped Evals/runs.'}
$manifestPath=Join-Path $runPath 'run-manifest.json';$m=Get-Content -Raw -Encoding UTF8 -LiteralPath $manifestPath|ConvertFrom-Json;$workspace=Join-Path $runPath $m.workspace
if(Test-Path (Join-Path $workspace 'hidden')){throw 'Hidden material leaked into agent workspace.'}
$changed=@();$initial=@{};foreach($f in $m.initial_files){$initial[$f.path]=$f.sha256};Get-ChildItem $workspace -File -Recurse|Where-Object{$_.FullName -notmatch '[\\/]\.agentic[\\/]' -and $_.FullName -notmatch '[\\/]__pycache__[\\/]' -and $_.Extension -ne '.pyc'}|ForEach-Object{$rel=$_.FullName.Substring($workspace.Length+1).Replace('\','/');$hash=(Get-FileHash $_.FullName -Algorithm SHA256).Hash;if(-not $initial.ContainsKey($rel)-or $initial[$rel]-ne $hash){$changed+=$rel}}
$protectedChanged=@();foreach($f in @($m.protected_initial_files)){ $target=Join-Path $workspace $f.path;if(-not(Test-Path -LiteralPath $target) -or (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $f.sha256){$protectedChanged+=$f.path} }
$python=(Get-Command python -ErrorAction Stop).Source
Push-Location $workspace
try { $previousErrorPreference=$ErrorActionPreference;$ErrorActionPreference='Continue';$publicOut=& $python @($m.public_test[1..($m.public_test.Count-1)]) 2>&1|Out-String;$publicExit=$LASTEXITCODE;$ErrorActionPreference=$previousErrorPreference }
finally { Pop-Location }
$grader=Join-Path $rootPath $m.central_hidden_grader
$graderSeed=20260713+[int]$m.trial;$previousGraderSeed=$env:AGENTIC_GRADER_SEED;$env:AGENTIC_GRADER_SEED=[string]$graderSeed
$previousErrorPreference=$ErrorActionPreference;$ErrorActionPreference='Continue';try{$hiddenOut=& $python $grader $workspace 2>&1|Out-String;$hiddenExit=$LASTEXITCODE}finally{$ErrorActionPreference=$previousErrorPreference;if($null -eq $previousGraderSeed){Remove-Item Env:AGENTIC_GRADER_SEED -ErrorAction SilentlyContinue}else{$env:AGENTIC_GRADER_SEED=$previousGraderSeed}}
$hiddenJson=Get-LastJson $hiddenOut
$failureKind=$null
if(-not ($hiddenJson -and ($hiddenJson.PSObject.Properties.Name -contains 'score'))){
    $hiddenJson=$null
    $looksLikeError=($hiddenOut -match '(?im)(Traceback \(most recent call last\)|ModuleNotFoundError|ImportError|SyntaxError|IndentationError|NameError|AttributeError:|TypeError:|KeyError:|ValueError:|Exception)')
    $referencesCandidate=($hiddenOut -match [regex]::Escape($workspace)) -or ($hiddenOut -match '(?im)[\\/]src[\\/]')
    if($looksLikeError -and $referencesCandidate){$failureKind='agent_crash'}else{$failureKind='grader_error'}
}
$enforcementPass=($m.arm -ne 'core-router-enforcement' -or $protectedChanged.Count -eq 0)
$outcomeValid=$hiddenJson -and $hiddenJson.PSObject.Properties.Name -contains 'score' -and [double]$hiddenJson.score -ge 0 -and [double]$hiddenJson.score -le 100 -and $enforcementPass
$qualityPassed=($publicExit -eq 0 -and [bool]$hiddenJson.passed -and $enforcementPass)
$executionPath=Join-Path $runPath 'provider-execution.json';$execution=if(Test-Path -LiteralPath $executionPath){Get-Content -Raw -Encoding UTF8 -LiteralPath $executionPath|ConvertFrom-Json}else{$null}
$tokenUsage=if($execution -and $execution.token_usage){$execution.token_usage}else{[ordered]@{total_observed_tokens=$Tokens;source='manual-parameter'}}
$monetaryCost=if($execution -and $execution.monetary_cost){$execution.monetary_cost}else{[ordered]@{amount_usd=if($Cost -gt 0){$Cost}else{$null};basis=if($Cost -gt 0){'manual-parameter'}else{'not-reported'}}}
$record=[ordered]@{schema_version=2;case_id=$m.fixture;arm=$m.arm;provider=$m.provider;requested_profile=$m.requested_model_profile;actual_model=$ActualModel;effort=$Effort;tokens=[long]$tokenUsage.total_observed_tokens;token_usage=$tokenUsage;cost=$monetaryCost.amount_usd;monetary_cost=$monetaryCost;started_at=$m.created_at;finished_at=[datetimeoffset]::Now.ToString('o');exit_code=if($qualityPassed){0}else{1};outcome_valid=[bool]$outcomeValid;quality_passed=[bool]$qualityPassed;isolation=$m.isolation;publishable_hidden_result=[bool]$m.publishable_hidden_result;changed_files=$changed;protected_files_changed=$protectedChanged;public_tests=[ordered]@{passed=($publicExit -eq 0);exit_code=$publicExit;output=$publicOut};grader=[ordered]@{passed=[bool]$hiddenJson.passed;score=[double]$hiddenJson.score;seed=$graderSeed;dimensions=if($hiddenJson.dimensions){$hiddenJson.dimensions}else{$null};checks=@($hiddenJson.checks);evidence=@($hiddenJson.checks|ForEach-Object{"$($_.id)=$($_.passed)"})};enforcement_passed=$enforcementPass;failure_kind=$failureKind}
$recordJson=$record|ConvertTo-Json -Depth 10
$schemaPath=Join-Path $rootPath 'Evals/adapters/run-record.schema.json'
if((Get-Command Test-Json -ErrorAction SilentlyContinue) -and (Test-Path -LiteralPath $schemaPath)){
    try{ $null=Test-Json -Json $recordJson -Schema (Get-Content -Raw -Encoding UTF8 -LiteralPath $schemaPath) -ErrorAction Stop }
    catch{ Write-Warning "run-record schema validation failed: $($_.Exception.Message)" }
}
$recordJson|Set-Content -Encoding UTF8 -LiteralPath (Join-Path $runPath 'run-record.json')
foreach($property in @([pscustomobject]@{name='status';value='graded'},[pscustomobject]@{name='actual_model';value=$ActualModel},[pscustomobject]@{name='effort';value=$Effort})){
    if($m.PSObject.Properties.Name -contains $property.name){$m.($property.name)=$property.value}else{$m|Add-Member -NotePropertyName $property.name -NotePropertyValue $property.value}
}
$m|ConvertTo-Json -Depth 10|Set-Content -Encoding UTF8 -LiteralPath $manifestPath
$record|ConvertTo-Json -Depth 10
if(-not $outcomeValid){exit 1}
