[CmdletBinding()]
param([string]$OutputPath)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$temp=Join-Path ([IO.Path]::GetTempPath()) ('benchmark-safety-'+[guid]::NewGuid().ToString('N'))
$results=@()
try{
    New-Item -ItemType Directory -Path $temp|Out-Null
    $lockPath=Join-Path $temp 'campaign.runner.lock'
    $first=[IO.File]::Open($lockPath,[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
    $secondRejected=$false
    try{try{$second=[IO.File]::Open($lockPath,[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)}catch{$secondRejected=$true}}finally{if($second){$second.Dispose()};$first.Dispose()}
    $results+=[pscustomobject]@{id='exclusive-campaign-lock';passed=$secondRejected}

    $providerLockPath=Join-Path $temp 'agenticbench-provider.lock'
    $first=[IO.File]::Open($providerLockPath,[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
    $secondRejected=$false;$second=$null
    try{try{$second=[IO.File]::Open($providerLockPath,[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)}catch{$secondRejected=$true}}finally{if($second){$second.Dispose()};$first.Dispose()}
    $results+=[pscustomobject]@{id='exclusive-provider-lock';passed=$secondRejected}

    $campaign=[ordered]@{schema_version=1;campaign_id='closed-test';status='closed-diagnostic-invalid';provider_snapshot=[ordered]@{expires_at=[datetimeoffset]::Now.AddDays(1).ToString('o');providers=@()};stages=@([ordered]@{id='smoke';status='diagnostic-invalid'});runs=@()}
    $campaign|ConvertTo-Json -Depth 8|Set-Content -Encoding UTF8 -LiteralPath (Join-Path $temp 'campaign.json')
    $old=$ErrorActionPreference;$ErrorActionPreference='Continue';$closedOut=& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'Evals/tools/approve-benchmark-stage.ps1') -Campaign $temp -Stage smoke -ApprovedBy test 2>&1|Out-String;$closedExit=$LASTEXITCODE;$ErrorActionPreference=$old
    $results+=[pscustomobject]@{id='closed-campaign-cannot-reopen';passed=($closedExit -ne 0 -and $closedOut -match 'Campaign is closed')}

    $campaign.status='awaiting-directional-approval';$campaign.provider_snapshot.providers=@([ordered]@{id='codex';model='provider-default'},[ordered]@{id='claude';model='provider-default'});$campaign.stages=@([ordered]@{id='smoke';status='complete'},[ordered]@{id='directional';status='awaiting-approval'});$campaign.runs=@()
    $campaign|ConvertTo-Json -Depth 8|Set-Content -Encoding UTF8 -LiteralPath (Join-Path $temp 'campaign.json')
    $old=$ErrorActionPreference;$ErrorActionPreference='Continue';$defaultOut=& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'Evals/tools/approve-benchmark-stage.ps1') -Campaign $temp -Stage directional -ApprovedBy test 2>&1|Out-String;$defaultExit=$LASTEXITCODE;$ErrorActionPreference=$old
    $results+=[pscustomobject]@{id='post-smoke-requires-explicit-models';passed=($defaultExit -ne 0 -and $defaultOut -match 'explicit model snapshots')}

    $settingsPath=Join-Path $temp 'provider-settings.json'
    [ordered]@{schema_version=1;generated_at=[datetimeoffset]::Now.ToString('o');expires_at=[datetimeoffset]::Now.AddDays(1).ToString('o');providers=@([ordered]@{id='codex';model='gpt-5.6-sol';effort='medium';cli_version='test'})}|ConvertTo-Json -Depth 6|Set-Content -Encoding UTF8 -LiteralPath $settingsPath
    $old=$ErrorActionPreference;$ErrorActionPreference='Continue';$calibrationOut=& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'Evals/tools/new-benchmark-calibration.ps1') -Root $root -ProviderSettings $settingsPath -OutputRoot $temp 2>&1|Out-String;$calibrationExit=$LASTEXITCODE;$ErrorActionPreference=$old
    $calibration=$null
    if($calibrationExit -eq 0){try{$calibration=$calibrationOut|ConvertFrom-Json}catch{}}
    $calibrationCampaign=$null
    if($calibration -and (Test-Path -LiteralPath (Join-Path $calibration.path 'campaign.json'))){$calibrationCampaign=Get-Content -Raw -LiteralPath (Join-Path $calibration.path 'campaign.json')|ConvertFrom-Json}
    $calibrationValid=$calibrationExit -eq 0 -and $calibration -and $calibrationCampaign -and $calibration.calls -eq 2 -and $calibration.additional_provider_calls -eq 0 -and $calibration.model -eq 'gpt-5.6-sol' -and $calibrationCampaign.status -eq 'awaiting-calibration-approval' -and @($calibrationCampaign.runs).Count -eq 2 -and @($calibrationCampaign.runs|Where-Object{$_.status -eq 'pending' -and -not $_.run_id}).Count -eq 2 -and @($calibrationCampaign.runs.arm|Sort-Object -Unique) -join ',' -eq 'core-router-enforcement,vanilla'
    $results+=[pscustomobject]@{id='calibration-manifest-exactly-two-pending-calls';passed=[bool]$calibrationValid}

    $codexEvents=Join-Path $temp 'codex-events.jsonl'
    [ordered]@{type='turn.completed';usage=[ordered]@{input_tokens=120;cached_input_tokens=80;output_tokens=30;reasoning_output_tokens=7}}|ConvertTo-Json -Compress -Depth 5|Set-Content -Encoding UTF8 -LiteralPath $codexEvents
    $claudeEvents=Join-Path $temp 'claude-events.jsonl'
    @(
        ([ordered]@{type='assistant';message=[ordered]@{model='claude-test'}}|ConvertTo-Json -Compress -Depth 5),
        ([ordered]@{type='result';total_cost_usd=0.125;usage=[ordered]@{input_tokens=2;cache_creation_input_tokens=10;cache_read_input_tokens=40;output_tokens=8}}|ConvertTo-Json -Compress -Depth 5)
    )|Set-Content -Encoding UTF8 -LiteralPath $claudeEvents
    $codexTelemetry=& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'Evals/tools/read-provider-telemetry.ps1') -EventsPath $codexEvents -Provider codex|ConvertFrom-Json
    $claudeTelemetry=& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'Evals/tools/read-provider-telemetry.ps1') -EventsPath $claudeEvents -Provider claude|ConvertFrom-Json
    $telemetryValid=$codexTelemetry.token_usage.total_observed_tokens -eq 150 -and $codexTelemetry.token_usage.cached_input_tokens -eq 80 -and $null -eq $codexTelemetry.monetary_cost.amount_usd -and $claudeTelemetry.actual_model -eq 'claude-test' -and $claudeTelemetry.token_usage.total_observed_tokens -eq 60 -and [double]$claudeTelemetry.monetary_cost.amount_usd -eq 0.125
    $results+=[pscustomobject]@{id='provider-telemetry-token-and-cost-accounting';passed=[bool]$telemetryValid}

    $partialRoot=Join-Path $temp 'partial-root';$partialRun=Join-Path $partialRoot 'Evals/runs/partial';$partialWorkspace=Join-Path $partialRun 'workspace';$partialGrader=Join-Path $partialRoot 'Evals/fixtures/production-ingestion-evolution/hidden'
    New-Item -ItemType Directory -Force -Path $partialWorkspace,$partialGrader|Out-Null
    Copy-Item -Path (Join-Path $root 'Evals/fixtures/production-ingestion-evolution/public/*') -Destination $partialWorkspace -Recurse -Force
    Copy-Item -Path (Join-Path $root 'Evals/fixtures/production-ingestion-evolution/hidden/negative-controls/generic-stateless/*') -Destination $partialWorkspace -Recurse -Force
    Copy-Item -LiteralPath (Join-Path $root 'Evals/fixtures/production-ingestion-evolution/hidden/grade.py') -Destination (Join-Path $partialGrader 'grade.py')
    [ordered]@{schema_version=1;run_id='partial';status='prepared';fixture='production-ingestion-evolution';arm='vanilla';provider='test';requested_model_profile='test';trial=1;created_at=[datetimeoffset]::Now.ToString('o');isolation='logical-only';publishable_hidden_result=$false;workspace='workspace';central_hidden_grader='Evals/fixtures/production-ingestion-evolution/hidden/grade.py';initial_files=@();protected_initial_files=@();public_test=@('python','-m','unittest','discover','-s','tests')}|ConvertTo-Json -Depth 8|Set-Content -Encoding UTF8 -LiteralPath (Join-Path $partialRun 'run-manifest.json')
    $old=$ErrorActionPreference;$ErrorActionPreference='Continue';$partialOut=& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'Evals/tools/grade-run.ps1') -Root $partialRoot -Run partial -ActualModel test-model -Effort medium 2>&1|Out-String;$partialExit=$LASTEXITCODE;$ErrorActionPreference=$old
    $partialRecord=if(Test-Path -LiteralPath (Join-Path $partialRun 'run-record.json')){Get-Content -Raw -LiteralPath (Join-Path $partialRun 'run-record.json')|ConvertFrom-Json}else{$null}
    $partialValid=$partialExit -eq 0 -and $partialRecord -and $partialRecord.outcome_valid -eq $true -and $partialRecord.quality_passed -eq $false -and [double]$partialRecord.grader.score -eq 85
    $results+=[pscustomobject]@{id='partial-quality-is-valid-scored-outcome';passed=[bool]$partialValid}

    # Fixture admission setup: the complex screen is only constructible over a
    # fixture holding a fresh outcome-harness validity record; produce one the
    # honest way (run the harness) when the newest record is stale.
    . (Join-Path $root 'Evals/tools/fixture-admission.ps1')
    if(-not (Get-FreshFixtureValidityRecord -RootPath $root -FixtureId 'production-ingestion-evolution')){& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'Evals/validate-outcome-harness.ps1') -Fixture production-ingestion-evolution|Out-Null}
    $complexRoot=Join-Path $temp 'complex-campaigns';New-Item -ItemType Directory -Path $complexRoot|Out-Null
    $old=$ErrorActionPreference;$ErrorActionPreference='Continue';$complexOut=& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'Evals/tools/new-complex-benchmark-screen.ps1') -Root $root -ProviderSettings $settingsPath -OutputRoot $complexRoot 2>&1|Out-String;$complexExit=$LASTEXITCODE;$ErrorActionPreference=$old
    $complex=$null;if($complexExit -eq 0){try{$complex=$complexOut|ConvertFrom-Json}catch{}}
    $complexCampaign=if($complex -and (Test-Path -LiteralPath (Join-Path $complex.path 'campaign.json'))){Get-Content -Raw -LiteralPath (Join-Path $complex.path 'campaign.json')|ConvertFrom-Json}else{$null}
    $complexValid=$complexExit -eq 0 -and $complex -and $complexCampaign -and $complex.calls -eq 6 -and $complex.additional_provider_calls -eq 0 -and $complexCampaign.status -eq 'awaiting-complex-screen-approval' -and @($complexCampaign.runs).Count -eq 6 -and @($complexCampaign.runs|Where-Object{$_.status -eq 'pending' -and -not $_.run_id}).Count -eq 6 -and @($complexCampaign.runs|Group-Object arm|Where-Object Count -eq 3).Count -eq 2 -and @($complexCampaign.runs.provider|Sort-Object -Unique) -join ',' -eq 'codex'
    $results+=[pscustomobject]@{id='complex-screen-manifest-six-paired-calls';passed=[bool]$complexValid}

    # --- Fixture admission: stage approval refuses a fixture without a fresh validity record, then admits once one exists ---
    $gateRoot=Join-Path $temp 'admission-root'
    $gateFixturePublic=Join-Path $gateRoot 'Evals/fixtures/demo-admission/public';$gateFixtureHidden=Join-Path $gateRoot 'Evals/fixtures/demo-admission/hidden'
    New-Item -ItemType Directory -Force -Path $gateFixturePublic,$gateFixtureHidden,(Join-Path $gateRoot 'Evals/reports'),(Join-Path $gateRoot 'Evals/runs')|Out-Null
    Set-Content -Encoding UTF8 -LiteralPath (Join-Path $gateFixturePublic 'task.md') -Value 'demo admission fixture'
    Set-Content -Encoding UTF8 -LiteralPath (Join-Path $gateFixtureHidden 'grade.py') -Value '# grader placeholder'
    [ordered]@{schema_version=1;fixtures=@([ordered]@{id='demo-admission-fixture';public_path='Evals/fixtures/demo-admission/public';hidden_grader='Evals/fixtures/demo-admission/hidden/grade.py';task_file='task.md';public_test=@('python','-m','unittest','discover','-s','tests')})}|ConvertTo-Json -Depth 6|Set-Content -Encoding UTF8 -LiteralPath (Join-Path $gateRoot 'Evals/fixtures/catalog.json')
    Get-ChildItem -LiteralPath (Join-Path $gateRoot 'Evals/fixtures') -Recurse -File|ForEach-Object{$_.LastWriteTime=(Get-Date).AddMinutes(-10)}
    $gateCampaignPath=Join-Path $gateRoot 'admission-campaign';New-Item -ItemType Directory -Path $gateCampaignPath|Out-Null
    [ordered]@{schema_version=2;campaign_id='admission-campaign';status='awaiting-smoke-approval';provider_snapshot=[ordered]@{expires_at=[datetimeoffset]::Now.AddDays(1).ToString('o');providers=@([ordered]@{id='codex';model='m1'},[ordered]@{id='claude';model='m2'})};stages=@([ordered]@{id='smoke';status='awaiting-approval';approved_at=$null;approved_by=$null});runs=@([ordered]@{run_key='smoke::demo-admission-fixture::codex::vanilla::t1';stage='smoke';fixture='demo-admission-fixture';provider='codex';arm='vanilla';trial=1;canary=$true;status='pending';run_id=$null})}|ConvertTo-Json -Depth 8|Set-Content -Encoding UTF8 -LiteralPath (Join-Path $gateCampaignPath 'campaign.json')
    $old=$ErrorActionPreference;$ErrorActionPreference='Continue';$refusedOut=& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'Evals/tools/approve-benchmark-stage.ps1') -Root $gateRoot -Campaign $gateCampaignPath -Stage smoke -ApprovedBy test 2>&1|Out-String;$refusedExit=$LASTEXITCODE;$ErrorActionPreference=$old
    $refusedValid=$refusedExit -ne 0 -and $refusedOut -match 'Fixture admission failed' -and $refusedOut -match 'demo-admission-fixture' -and $refusedOut -match 'validate-outcome-harness'
    [ordered]@{schema_version=2;run_at=[datetimeoffset]::Now.ToString('o');phase_timeout_seconds=15;cases=1;passed=1;failed=0;results=@([ordered]@{id='demo-admission-fixture';passed=$true})}|ConvertTo-Json -Depth 6|Set-Content -Encoding UTF8 -LiteralPath (Join-Path $gateRoot 'Evals/reports/synthetic-outcome-harness.json')
    $old=$ErrorActionPreference;$ErrorActionPreference='Continue';& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'Evals/tools/approve-benchmark-stage.ps1') -Root $gateRoot -Campaign $gateCampaignPath -Stage smoke -ApprovedBy test 2>&1|Out-Null;$admittedExit=$LASTEXITCODE;$ErrorActionPreference=$old
    $gateAfter=Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $gateCampaignPath 'campaign.json')|ConvertFrom-Json
    $results+=[pscustomobject]@{id='admission-refuses-unvalidated-fixture-then-admits';passed=[bool]($refusedValid -and $admittedExit -eq 0 -and @($gateAfter.stages|Where-Object{$_.id -eq 'smoke' -and $_.status -eq 'approved'}).Count -eq 1)}

    # --- Canary rule: campaign creation marks zero-paid-history fixtures canary with a stage-1 cap of one run ---
    $canaryRoot=Join-Path $temp 'canary-root'
    foreach($sub in @('Evals/tools','Evals/adapters/providers','Evals/fixtures/entity-parser/public','Evals/fixtures/entity-parser/hidden','Evals/fixtures/objective-omission/public','Evals/fixtures/objective-omission/hidden','Evals/reports','Evals/runs','Evals/experiments','Evals/local')){New-Item -ItemType Directory -Force -Path (Join-Path $canaryRoot $sub)|Out-Null}
    foreach($harness in @('Evals/tools/new-run.ps1','Evals/tools/grade-run.ps1','Evals/tools/run-benchmark-stage.ps1','Evals/adapters/providers/invoke-agenticbench.ps1')){Copy-Item -LiteralPath (Join-Path $root $harness) -Destination (Join-Path $canaryRoot $harness) -Force}
    foreach($fx in @(@{id='entity-parser-unseen';dir='entity-parser'},@{id='objective-omission';dir='objective-omission'})){
        Set-Content -Encoding UTF8 -LiteralPath (Join-Path $canaryRoot "Evals/fixtures/$($fx.dir)/public/task.md") -Value 'synthetic canary fixture'
        Set-Content -Encoding UTF8 -LiteralPath (Join-Path $canaryRoot "Evals/fixtures/$($fx.dir)/hidden/grade.py") -Value '# grader placeholder'
    }
    [ordered]@{schema_version=1;fixtures=@([ordered]@{id='entity-parser-unseen';public_path='Evals/fixtures/entity-parser/public';hidden_grader='Evals/fixtures/entity-parser/hidden/grade.py';task_file='task.md';public_test=@('python','-m','unittest','discover','-s','tests')},[ordered]@{id='objective-omission';public_path='Evals/fixtures/objective-omission/public';hidden_grader='Evals/fixtures/objective-omission/hidden/grade.py';task_file='task.md';public_test=@('python','-m','unittest','discover','-s','tests')})}|ConvertTo-Json -Depth 6|Set-Content -Encoding UTF8 -LiteralPath (Join-Path $canaryRoot 'Evals/fixtures/catalog.json')
    Get-ChildItem -LiteralPath (Join-Path $canaryRoot 'Evals/fixtures') -Recurse -File|ForEach-Object{$_.LastWriteTime=(Get-Date).AddMinutes(-10)}
    [ordered]@{schema_version=2;run_at=[datetimeoffset]::Now.ToString('o');phase_timeout_seconds=15;cases=2;passed=2;failed=0;results=@([ordered]@{id='entity-parser-unseen';passed=$true},[ordered]@{id='objective-omission';passed=$true})}|ConvertTo-Json -Depth 6|Set-Content -Encoding UTF8 -LiteralPath (Join-Path $canaryRoot 'Evals/reports/synthetic-outcome-harness.json')
    $canarySettings=Join-Path $canaryRoot 'Evals/local/provider-settings.json'
    [ordered]@{schema_version=1;generated_at=[datetimeoffset]::Now.ToString('o');expires_at=[datetimeoffset]::Now.AddDays(1).ToString('o');providers=@([ordered]@{id='codex';model='m1';effort='medium';cli_version='test'},[ordered]@{id='claude';model='m2';effort='medium';cli_version='test'})}|ConvertTo-Json -Depth 6|Set-Content -Encoding UTF8 -LiteralPath $canarySettings
    $old=$ErrorActionPreference;$ErrorActionPreference='Continue';$canaryOut=& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'Evals/tools/new-benchmark-campaign.ps1') -Root $canaryRoot -ProviderSettings $canarySettings 2>&1|Out-String;$canaryExit=$LASTEXITCODE;$ErrorActionPreference=$old
    $canaryCreated=$null;if($canaryExit -eq 0){try{$canaryCreated=$canaryOut|ConvertFrom-Json}catch{}}
    $canaryCampaign=if($canaryCreated -and (Test-Path -LiteralPath (Join-Path $canaryCreated.path 'campaign.json'))){Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $canaryCreated.path 'campaign.json')|ConvertFrom-Json}else{$null}
    $canaryValid=$canaryExit -eq 0 -and $canaryCampaign -and $canaryCampaign.canary_policy.stage1_cap_per_fixture -eq 1 -and (@($canaryCampaign.canary_policy.canary_fixtures|Sort-Object) -join ',') -eq 'entity-parser-unseen,objective-omission' -and @($canaryCampaign.runs|Where-Object{-not [bool]$_.canary}).Count -eq 0
    $results+=[pscustomobject]@{id='canary-cap-forced-for-zero-paid-history-fixture';passed=[bool]$canaryValid}

    # --- Canary rule: stage 2+ refuses to start without a validated canary run-record, then unblocks with one ---
    $stage2Path=Join-Path $canaryRoot 'Evals/experiments/stage2-campaign';New-Item -ItemType Directory -Force -Path $stage2Path,(Join-Path $canaryRoot 'Evals/runs/demo-canary-run')|Out-Null
    [ordered]@{schema_version=2;campaign_id='stage2-campaign';status='directional-approved';provider_snapshot=[ordered]@{expires_at=[datetimeoffset]::Now.AddDays(1).ToString('o');providers=@([ordered]@{id='codex';model='m1';effort='medium'})};loop=[ordered]@{max_consecutive_failures=2;max_no_progress=2;max_wall_minutes_per_run=15;max_turns_per_run=12};stages=@([ordered]@{id='smoke';status='complete'},[ordered]@{id='directional';status='approved'});runs=@([ordered]@{run_key='smoke::demo-canary::codex::vanilla::t1';stage='smoke';fixture='demo-canary';provider='codex';arm='vanilla';trial=1;canary=$true;status='provider_failed';run_id='demo-canary-run'},[ordered]@{run_key='directional::demo-canary::codex::vanilla::t1';stage='directional';fixture='demo-canary';provider='codex';arm='vanilla';trial=1;canary=$true;status='pending';run_id=$null})}|ConvertTo-Json -Depth 8|Set-Content -Encoding UTF8 -LiteralPath (Join-Path $stage2Path 'campaign.json')
    [ordered]@{schema_version=2;case_id='demo-canary';provider='codex-agenticbench';outcome_valid=$false;grader=[ordered]@{passed=$false;score=0;checks=@([ordered]@{id='only-check';dimension='functional';passed=$false;weight=1})}}|ConvertTo-Json -Depth 6|Set-Content -Encoding UTF8 -LiteralPath (Join-Path $canaryRoot 'Evals/runs/demo-canary-run/run-record.json')
    $old=$ErrorActionPreference;$ErrorActionPreference='Continue';$blockedOut=& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'Evals/tools/run-benchmark-stage.ps1') -Root $canaryRoot -Campaign $stage2Path -Stage directional 2>&1|Out-String;$blockedExit=$LASTEXITCODE;$ErrorActionPreference=$old
    $blockedValid=$blockedExit -ne 0 -and $blockedOut -match 'Canary gate' -and $blockedOut -match 'demo-canary'
    [ordered]@{schema_version=2;case_id='demo-canary';provider='codex-agenticbench';outcome_valid=$true;grader=[ordered]@{passed=$true;score=100;checks=@([ordered]@{id='check-a';dimension='functional';passed=$true;weight=1},[ordered]@{id='check-b';dimension='security';passed=$true;weight=1})}}|ConvertTo-Json -Depth 6|Set-Content -Encoding UTF8 -LiteralPath (Join-Path $canaryRoot 'Evals/runs/demo-canary-run/run-record.json')
    $old=$ErrorActionPreference;$ErrorActionPreference='Continue';$unblockedOut=& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'Evals/tools/run-benchmark-stage.ps1') -Root $canaryRoot -Campaign $stage2Path -Stage directional 2>&1|Out-String;$unblockedExit=$LASTEXITCODE;$ErrorActionPreference=$old
    $unblockedValid=$unblockedExit -ne 0 -and $unblockedOut -notmatch 'Canary gate' -and $unblockedOut -match 'doctor'
    $results+=[pscustomobject]@{id='stage2-refused-without-validated-canary-record';passed=[bool]($blockedValid -and $unblockedValid)}

    # --- Platform lint: catches an injected host-side python3 in a sandbox and stays green on the real tree ---
    $lintRoot=Join-Path $temp 'lint-root';New-Item -ItemType Directory -Force -Path (Join-Path $lintRoot 'Evals/tools')|Out-Null
    $bannedInterpreter='python'+'3'
    Set-Content -Encoding UTF8 -LiteralPath (Join-Path $lintRoot 'Evals/tools/bad-host-contract.ps1') -Value ("& $bannedInterpreter -m pytest")
    Set-Content -Encoding UTF8 -LiteralPath (Join-Path $lintRoot 'Evals/tools/wsl-command-builder.ps1') -Value ("wsl -d Ubuntu -- $bannedInterpreter --version")
    $old=$ErrorActionPreference;$ErrorActionPreference='Continue';$lintDirtyOut=& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'Evals/tools/check-platform-portability.ps1') -Root $lintRoot 2>&1|Out-String;$lintDirtyExit=$LASTEXITCODE;$ErrorActionPreference=$old
    $lintDirty=$null;try{$lintDirty=$lintDirtyOut|ConvertFrom-Json}catch{}
    $lintDirtyValid=$lintDirtyExit -eq 1 -and $lintDirty -and @($lintDirty.findings|Where-Object{$_.file -match 'bad-host-contract' -and $_.line -eq 1 -and $_.pattern -match 'host-alias'}).Count -ge 1 -and @($lintDirty.findings|Where-Object{$_.file -match 'wsl-command-builder'}).Count -eq 0 -and @($lintDirty.wsl_context_notes|Where-Object{$_.file -match 'wsl-command-builder'}).Count -ge 1
    $results+=[pscustomobject]@{id='platform-lint-flags-injected-host-interpreter';passed=[bool]$lintDirtyValid}
    $old=$ErrorActionPreference;$ErrorActionPreference='Continue';$lintCleanOut=& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'Evals/tools/check-platform-portability.ps1') -OutputPath (Join-Path $temp 'lint-clean.json') 2>&1|Out-String;$lintCleanExit=$LASTEXITCODE;$ErrorActionPreference=$old
    $lintClean=$null;try{$lintClean=$lintCleanOut|ConvertFrom-Json}catch{}
    $results+=[pscustomobject]@{id='platform-lint-clean-on-stable-tree';passed=[bool]($lintCleanExit -eq 0 -and $lintClean -and $lintClean.failed -eq 0 -and $lintClean.cases -ge 20)}
}finally{if(Test-Path -LiteralPath $temp){Remove-Item -LiteralPath $temp -Recurse -Force}}
$failed=@($results|Where-Object{-not $_.passed}).Count
$report=[ordered]@{schema_version=1;run_at=[datetimeoffset]::Now.ToString('o');cases=$results.Count;passed=$results.Count-$failed;failed=$failed;results=$results}
if(-not $OutputPath){$OutputPath=Join-Path $root ("Evals/reports/{0}-benchmark-safety.json" -f (Get-Date -Format 'yyyy-MM-dd-HHmmss'))}
$report|ConvertTo-Json -Depth 8|Set-Content -Encoding UTF8 -LiteralPath $OutputPath
$report|ConvertTo-Json -Depth 8
if($failed){exit 1}
