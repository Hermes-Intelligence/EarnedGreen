[CmdletBinding()]
param([ValidateSet('infrastructure','full')][string]$Mode='infrastructure',[string]$OutputPath)
$ErrorActionPreference='Stop';$root=Split-Path -Parent $PSScriptRoot;$checks=@()
function Run-JsonTest([string]$id,[string]$script){$old=$ErrorActionPreference;$ErrorActionPreference='Continue';$out=& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root $script) 2>&1|Out-String;$code=$LASTEXITCODE;$ErrorActionPreference=$old;$json=$null;if($code -eq 0){try{$json=$out|ConvertFrom-Json}catch{}};$script:checks+=[pscustomobject]@{id=$id;passed=($code -eq 0 -and $json -and [int]$json.failed -eq 0);exit_code=$code;summary=if($json){"$($json.passed)/$($json.cases)"}else{'no valid report'}}}
$jsonFiles=Get-ChildItem $root -Recurse -Filter *.json|Where-Object{$_.FullName -notmatch '[\\/]\.git[\\/]' -and $_.FullName -notmatch '[\\/]Evals[\\/]runs[\\/]'};$jsonErrors=@();foreach($f in $jsonFiles){try{Get-Content $f.FullName -Raw|ConvertFrom-Json|Out-Null}catch{$jsonErrors+=$f.FullName}};$checks+=[pscustomobject]@{id='json-parse';passed=($jsonErrors.Count -eq 0);exit_code=if($jsonErrors.Count){1}else{0};summary="$($jsonFiles.Count) files, $($jsonErrors.Count) errors"}
$psFiles=Get-ChildItem $root -Recurse -Filter *.ps1|Where-Object{$_.FullName -notmatch '[\\/]Evals[\\/]runs[\\/]'};$parse=@();foreach($f in $psFiles){$t=$null;$e=$null;[Management.Automation.Language.Parser]::ParseFile($f.FullName,[ref]$t,[ref]$e)|Out-Null;if($e){$parse+=$e}};$checks+=[pscustomobject]@{id='powershell-parse';passed=($parse.Count -eq 0);exit_code=if($parse.Count){1}else{0};summary="$($psFiles.Count) files, $($parse.Count) errors"}
Run-JsonTest 'knowledge-routing' 'Evals/run-evals.ps1';Run-JsonTest 'model-routing' 'Evals/run-model-routing.ps1';Run-JsonTest 'runtime-controls' 'Evals/test-runtime-controls.ps1';Run-JsonTest 'fixture-discrimination' 'Evals/validate-outcome-harness.ps1';Run-JsonTest 'run-lifecycle' 'Evals/test-run-lifecycle.ps1';Run-JsonTest 'real-world-battery-lifecycle' 'Evals/test-real-world-battery.ps1';Run-JsonTest 'benchmark-safety' 'Evals/test-benchmark-safety.ps1';Run-JsonTest 'security-hooks' 'Evals/test-security-hooks.ps1';Run-JsonTest 'windows-platform' 'Evals/test-windows-platform.ps1';Run-JsonTest 'wsl-isolation' 'Evals/test-wsl-isolation.ps1';Run-JsonTest 'secret-hygiene' 'Evals/tools/check-secret-hygiene.ps1';Run-JsonTest 'platform-portability' 'Evals/tools/check-platform-portability.ps1'
$doctor=& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'tools/doctor.ps1') -TargetRepo $root -Json|ConvertFrom-Json;$checks+=[pscustomobject]@{id='doctor';passed=[bool]$doctor.passed;exit_code=if($doctor.passed){0}else{2};summary="failures=$($doctor.failures), warnings=$($doctor.warnings)"}
if($Mode -eq 'full'){
    $objective=Get-Content -Raw (Join-Path $root 'Objectives/active/OBJ-20260712-agentic-work-best-practices.json')|ConvertFrom-Json
    $open=@($objective.pillars.requirements|Where-Object{$_.status -ne 'verified' -and $_.status -ne 'not_applicable' -and $_.status -ne 'rejected'})
    $fixtures=(Get-Content -Raw (Join-Path $root 'Evals/fixtures/catalog.json')|ConvertFrom-Json).fixtures
    $checks+=[pscustomobject]@{id='objective-complete';passed=($open.Count -eq 0);exit_code=if($open.Count){1}else{0};summary="$($open.Count) open requirements"}
    $checks+=[pscustomobject]@{id='twelve-executable-fixtures';passed=($fixtures.Count -ge 12);exit_code=if($fixtures.Count -ge 12){0}else{1};summary="$($fixtures.Count)/12 fixtures"}
    $agenticBench=Join-Path $root 'Evals/local/agenticbench-status.json'
    $providerValid=$false
    $proofValid=$false
    if(Test-Path $agenticBench){
        try{
            $local=Get-Content -Raw $agenticBench|ConvertFrom-Json
            $providerValid=$local.ready -eq $true
            $proofValid=@($local.checks|Where-Object{$_.id -eq 'windows-drive-not-mounted' -and $_.status -eq 'PASS'}).Count -eq 1
        }catch{}
    }
    $checks+=[pscustomobject]@{id='verified-provider-config';passed=$providerValid;exit_code=if($providerValid){0}else{1};summary=if($providerValid){'Codex and Claude authenticated in AgenticBench'}else{'AgenticBench provider logins missing'}}
    $checks+=[pscustomobject]@{id='secure-isolation-proof';passed=$proofValid;exit_code=if($proofValid){0}else{1};summary=if($proofValid){'dedicated WSL with Windows drive unmounted'}else{'AgenticBench isolation proof missing'}}
}
$failed=@($checks|Where-Object{-not $_.passed}).Count;$report=[ordered]@{schema_version=1;run_at=[datetimeoffset]::Now.ToString('o');mode=$Mode;passed=($failed -eq 0);checks_passed=$checks.Count-$failed;checks_failed=$failed;checks=$checks}
if(-not $OutputPath){$OutputPath=Join-Path $root ("Evals/reports/{0}-release-gate-{1}.json" -f (Get-Date -Format 'yyyy-MM-dd-HHmmss'),$Mode)};$report|ConvertTo-Json -Depth 8|Set-Content -Encoding UTF8 $OutputPath;$report|ConvertTo-Json -Depth 8;if($failed){exit 1}
