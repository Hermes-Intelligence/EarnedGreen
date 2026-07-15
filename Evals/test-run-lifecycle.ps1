[CmdletBinding()]
param([string]$OutputPath)
$ErrorActionPreference='Stop';$root=Split-Path -Parent $PSScriptRoot;$results=@();$created=@()
try{
    foreach($spec in @(@{fixture='entity-parser-unseen';arm='vanilla'},@{fixture='objective-omission';arm='core-router-enforcement'})){
        $prepared=& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'Evals/tools/new-run.ps1') -Fixture $spec.fixture -Arm $spec.arm -Provider validation -ModelProfile balanced-daily -Trial 1 -Isolation logical-only|ConvertFrom-Json;$created+=$prepared.run_path
        $catalog=Get-Content -Raw (Join-Path $root 'Evals/fixtures/catalog.json')|ConvertFrom-Json;$fixture=@($catalog.fixtures|Where-Object id -eq $spec.fixture)[0];$reference=Join-Path $root ((Split-Path -Parent $fixture.hidden_grader)+'/reference/*');Copy-Item -Path $reference -Destination $prepared.workspace -Recurse -Force
        if($spec.arm -eq 'core-router-enforcement'){Set-Content -Encoding UTF8 -LiteralPath (Join-Path $prepared.workspace 'tests/test_regression.py') -Value '# A newly added regression test is allowed by enforcement.'}
        $record=& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'Evals/tools/grade-run.ps1') -Run $prepared.run_id -ActualModel validation-reference -Effort medium|ConvertFrom-Json
        $hiddenLeak=Test-Path (Join-Path $prepared.workspace 'hidden')
        $regressionAllowed=($spec.arm -ne 'core-router-enforcement' -or ('tests/test_regression.py' -in @($record.changed_files) -and @($record.protected_files_changed).Count -eq 0 -and $record.enforcement_passed))
        $results+=[pscustomobject]@{id=($spec.fixture+'-'+$spec.arm);passed=($record.grader.passed -and $record.public_tests.passed -and -not $record.publishable_hidden_result -and -not $hiddenLeak -and $regressionAllowed);score=$record.grader.score;publishable=$record.publishable_hidden_result}
    }

    $tamper=& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'Evals/tools/new-run.ps1') -Fixture entity-parser-unseen -Arm core-router-enforcement -Provider validation -ModelProfile balanced-daily -Trial 2 -Isolation logical-only|ConvertFrom-Json;$created+=$tamper.run_path
    $catalog=Get-Content -Raw (Join-Path $root 'Evals/fixtures/catalog.json')|ConvertFrom-Json;$fixture=@($catalog.fixtures|Where-Object id -eq 'entity-parser-unseen')[0];Copy-Item -Path (Join-Path $root ((Split-Path -Parent $fixture.hidden_grader)+'/reference/*')) -Destination $tamper.workspace -Recurse -Force
    Add-Content -Encoding UTF8 -LiteralPath (Join-Path $tamper.workspace 'tests/test_public.py') -Value '# deliberate integrity tamper'
    $old=$ErrorActionPreference;$ErrorActionPreference='Continue';$tamperRaw=& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'Evals/tools/grade-run.ps1') -Run $tamper.run_id -ActualModel validation-reference -Effort medium 2>&1|Out-String;$tamperExit=$LASTEXITCODE;$ErrorActionPreference=$old
    $tamperRecord=$tamperRaw|ConvertFrom-Json
    $results+=[pscustomobject]@{id='enforcement-rejects-existing-public-test-tamper';passed=($tamperExit -eq 1 -and $tamperRecord.public_tests.passed -and $tamperRecord.grader.passed -and -not $tamperRecord.enforcement_passed -and 'tests/test_public.py' -in @($tamperRecord.protected_files_changed));score=$tamperRecord.grader.score;publishable=$tamperRecord.publishable_hidden_result}
}finally{foreach($path in $created){if(Test-Path $path){Remove-Item $path -Recurse -Force}}}
$failed=@($results|Where-Object{-not $_.passed}).Count;$report=[ordered]@{schema_version=1;run_at=[datetimeoffset]::Now.ToString('o');cases=$results.Count;passed=$results.Count-$failed;failed=$failed;results=$results}
if(-not $OutputPath){$OutputPath=Join-Path $root ("Evals/reports/{0}-run-lifecycle.json" -f (Get-Date -Format 'yyyy-MM-dd-HHmmss'))};$report|ConvertTo-Json -Depth 8|Set-Content -Encoding UTF8 $OutputPath;$report|ConvertTo-Json -Depth 8;if($failed){exit 1}
