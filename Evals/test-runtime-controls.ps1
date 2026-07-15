[CmdletBinding()]
param([string]$OutputPath)
$ErrorActionPreference="Stop"
$repo=Split-Path -Parent $PSScriptRoot
$sandbox=Join-Path ([IO.Path]::GetTempPath()) ("agentic-controls-"+[guid]::NewGuid().ToString('N'))
$results=@()
try {
    New-Item -ItemType Directory -Force -Path (Join-Path $sandbox 'Runtime/stable'),(Join-Path $sandbox 'Research/candidate-packages/test-candidate/promotion/payload'),(Join-Path $sandbox 'Runtime/releases'),(Join-Path $sandbox 'Models')|Out-Null
    Set-Content -Encoding UTF8 -LiteralPath (Join-Path $sandbox 'Runtime/stable/manifest.json') -Value '{"release":"0.1.0"}'
    Set-Content -Encoding UTF8 -LiteralPath (Join-Path $sandbox 'Models/providers.json') -Value '{"version":"old"}'
    $candidate=Join-Path $sandbox 'Research/candidate-packages/test-candidate'
    foreach($name in @('claims.json','rejected-claims.json')){Set-Content -Encoding UTF8 -LiteralPath (Join-Path $candidate $name) -Value '[]'}
    Set-Content -Encoding UTF8 -LiteralPath (Join-Path $candidate 'source-registry.patch.json') -Value '{}'
    Set-Content -Encoding UTF8 -LiteralPath (Join-Path $candidate 'eval-plan.json') -Value '{}'
    Set-Content -Encoding UTF8 -LiteralPath (Join-Path $candidate 'proposed-changes.md') -Value '# Change'
    Set-Content -Encoding UTF8 -LiteralPath (Join-Path $candidate 'report.md') -Value '# Report'
    Set-Content -Encoding Byte -LiteralPath (Join-Path $candidate 'report.pdf') -Value ([byte[]](37,80,68,70))
    Set-Content -Encoding UTF8 -LiteralPath (Join-Path $candidate 'run-manifest.json') -Value '{"status":"awaiting-eval"}'
    Set-Content -Encoding UTF8 -LiteralPath (Join-Path $candidate 'eval-result.json') -Value '{"passed":2,"failed":0}'
    $payload=Join-Path $candidate 'promotion/payload/providers.json'; Set-Content -Encoding UTF8 -LiteralPath $payload -Value '{"version":"new"}'
    $promotion=[ordered]@{schema_version=1;candidate_id='test-candidate';release='0.2.0-test';status='awaiting-approval';stable_manifest_before_sha256=(Get-FileHash (Join-Path $sandbox 'Runtime/stable/manifest.json') -Algorithm SHA256).Hash;required_evals=@([ordered]@{report='eval-result.json';minimum_passed=2;maximum_failed=0});files=@([ordered]@{source='promotion/payload/providers.json';target='Models/providers.json';before_sha256=(Get-FileHash (Join-Path $sandbox 'Models/providers.json') -Algorithm SHA256).Hash;after_sha256=(Get-FileHash $payload -Algorithm SHA256).Hash})}
    $promotion|ConvertTo-Json -Depth 8|Set-Content -Encoding UTF8 -LiteralPath (Join-Path $candidate 'promotion/manifest.json')
    $old=$ErrorActionPreference;$ErrorActionPreference='Continue';$preview=& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repo 'tools/promote-candidate.ps1') -Candidate test-candidate -Root $sandbox 2>&1|Out-String;$previewExit=$LASTEXITCODE;$ErrorActionPreference=$old
    $previewPass=$previewExit -eq 3 -and (Get-Content (Join-Path $sandbox 'Models/providers.json') -Raw).Contains('old')
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repo 'tools/promote-candidate.ps1') -Candidate test-candidate -Root $sandbox -Approve -ApprovedBy eval -SkipReleaseGate -SkipReleaseGateReason 'runtime-controls sandbox exercises promotion/rollback mechanics, not the release gate'|Out-Null
    $promoted=(Get-Content (Join-Path $sandbox 'Models/providers.json') -Raw).Contains('new')
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repo 'tools/rollback-release.ps1') -Release '0.2.0-test' -Root $sandbox -Approve -ApprovedBy eval|Out-Null
    $rolledBack=(Get-Content (Join-Path $sandbox 'Models/providers.json') -Raw).Contains('old')
    $results+=[pscustomobject]@{id='promotion-preview-no-write';passed=$previewPass}
    $results+=[pscustomobject]@{id='promotion-and-rollback';passed=($promoted -and $rolledBack)}

    $loopDir=Join-Path $sandbox 'loop';New-Item -ItemType Directory -Path $loopDir|Out-Null
    $loop=[ordered]@{id='test-loop';objective='Reach a deterministic verified final state.';budgets=[ordered]@{max_iterations=10;max_failures=2;max_no_progress=2;max_seconds=600;max_cost=10};progress=[ordered]@{end_state='verified';fingerprint_definition='artifact hash';escalation='human'};kill_file='STOP';state_path='state.json'}
    $loop|ConvertTo-Json -Depth 6|Set-Content -Encoding UTF8 -LiteralPath (Join-Path $loopDir 'manifest.json')
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repo 'tools/loop-checkpoint.ps1') -ManifestPath (Join-Path $loopDir 'manifest.json') -Action start|Out-Null
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repo 'tools/loop-checkpoint.ps1') -ManifestPath (Join-Path $loopDir 'manifest.json') -Action progress -Fingerprint same|Out-Null
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repo 'tools/loop-checkpoint.ps1') -ManifestPath (Join-Path $loopDir 'manifest.json') -Action progress -Fingerprint same|Out-Null
    $old=$ErrorActionPreference;$ErrorActionPreference='Continue';& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repo 'tools/loop-checkpoint.ps1') -ManifestPath (Join-Path $loopDir 'manifest.json') -Action progress -Fingerprint same 2>&1|Out-Null;$loopExit=$LASTEXITCODE;$ErrorActionPreference=$old
    $loopState=Get-Content (Join-Path $loopDir 'state.json') -Raw|ConvertFrom-Json
    $results+=[pscustomobject]@{id='loop-no-progress-stop';passed=($loopExit -eq 4 -and $loopState.stop_reason -eq 'no-progress')}

    $handoff=[ordered]@{schema_version=1;objective_id='OBJ-test';task='Continue controlled implementation';status='in_progress';updated_at=[datetimeoffset]::Now.ToString('o');decisions=@([ordered]@{id='D1';decision='Use isolation';reason='Prevent leakage'});evidence=@([ordered]@{claim='Harness created';artifact='Evals/README.md'});blockers=@();next_action='Run the hidden fixture pilot.';changed_paths=@('Evals/');requirements=@([ordered]@{id='REQ-EVAL-001';status='in_progress';evidence=@()})}
    $handoffPath=Join-Path $sandbox 'handoff.json';$handoff|ConvertTo-Json -Depth 8|Set-Content -Encoding UTF8 -LiteralPath $handoffPath
    $handoffResult=& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repo 'tools/handoff-check.ps1') -HandoffPath $handoffPath|ConvertFrom-Json
    $results+=[pscustomobject]@{id='handoff-valid';passed=$handoffResult.valid}

    $pluralRoute=& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repo 'tools/route.ps1') -Task 'Rotate credentials, isolate secrets and prevent leaked tokens.' -Repo $repo -NoWrite|ConvertFrom-Json
    $results+=[pscustomobject]@{id='router-plural-security-terms';passed=($pluralRoute.fingerprint.risk -eq 'high' -and 'security-boundaries' -in @($pluralRoute.selected_modules.id))}
} finally { if(Test-Path $sandbox){Remove-Item -LiteralPath $sandbox -Recurse -Force} }
$failed=@($results|Where-Object{-not $_.passed}).Count
$report=[ordered]@{schema_version=1;run_at=(Get-Date).ToString('o');cases=$results.Count;passed=$results.Count-$failed;failed=$failed;results=$results}
if(-not $OutputPath){$OutputPath=Join-Path $repo ("Evals/reports/{0}-runtime-controls.json" -f (Get-Date -Format 'yyyy-MM-dd-HHmmss'))}
$report|ConvertTo-Json -Depth 8|Set-Content -Encoding UTF8 -LiteralPath $OutputPath
$report|ConvertTo-Json -Depth 8
if($failed){exit 1}
