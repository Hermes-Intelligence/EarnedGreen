[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Fixture,
    [Parameter(Mandatory=$true)][ValidateSet("vanilla","core","core-router","core-router-enforcement")][string]$Arm,
    [string]$Provider="manual",
    [string]$ModelProfile="balanced-daily",
    [int]$Trial=1,
    [ValidateSet("logical-only","container","vm","dedicated-wsl")][string]$Isolation="logical-only",
    [string]$Root
)
$ErrorActionPreference="Stop"
if(-not $Root){$Root=Split-Path -Parent (Split-Path -Parent $PSScriptRoot)}
$rootPath=(Resolve-Path $Root).Path
$catalog=Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $rootPath 'Evals/fixtures/catalog.json')|ConvertFrom-Json
$fixtureDef=@($catalog.fixtures|Where-Object id -eq $Fixture)[0];if(-not $fixtureDef){throw "Unknown fixture: $Fixture"}
$public=(Resolve-Path (Join-Path $rootPath $fixtureDef.public_path)).Path
$stamp=Get-Date -Format 'yyyyMMdd-HHmmssfff';$runId="$stamp-$Fixture-$Arm-t$Trial";$runPath=Join-Path $rootPath "Evals/runs/$runId";$workspace=Join-Path $runPath 'workspace'
New-Item -ItemType Directory -Force -Path $workspace,(Join-Path $runPath 'artifacts')|Out-Null
Copy-Item -Path (Join-Path $public '*') -Destination $workspace -Recurse -Force
$agentic=Join-Path $workspace '.agentic';New-Item -ItemType Directory -Force -Path $agentic|Out-Null
$task=Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $workspace $fixtureDef.task_file)
$contextFiles=@()
if($Arm -ne 'vanilla') { Copy-Item -LiteralPath (Join-Path $rootPath 'Core/runtime.md') -Destination (Join-Path $agentic 'CORE.md');$contextFiles+='CORE.md' }
if($Arm -in @('core-router','core-router-enforcement')) {
    $route=& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $rootPath 'tools/route.ps1') -Task $task -Repo $workspace -NoWrite|ConvertFrom-Json
    $route|ConvertTo-Json -Depth 10|Set-Content -Encoding UTF8 -LiteralPath (Join-Path $agentic 'context-pack.json');$contextFiles+='context-pack.json'
    $moduleDir=Join-Path $agentic 'modules';New-Item -ItemType Directory -Path $moduleDir|Out-Null
    foreach($module in $route.selected_modules){$src=Join-Path $rootPath $module.path;if(Test-Path $src){$name=($module.id+'.md');Copy-Item $src (Join-Path $moduleDir $name);$contextFiles+="modules/$name"}}
}
if($Arm -eq 'core-router-enforcement') {
    $protectedFiles=@($fixtureDef.task_file)
    $fixtureTests=Join-Path $workspace 'tests'
    if(Test-Path -LiteralPath $fixtureTests){$protectedFiles+=@(Get-ChildItem -LiteralPath $fixtureTests -File -Recurse|ForEach-Object{$_.FullName.Substring($workspace.Length+1).Replace('\','/')})}
    [ordered]@{schema_version=1;protected_files=@($protectedFiles|Sort-Object -Unique);new_regression_tests_allowed=$true;generated_artifacts_ignored=@('__pycache__','*.pyc');required_public_test=$fixtureDef.public_test;completion_requires=@('public tests pass','hidden grader runs on host','changed files reviewed')}|ConvertTo-Json -Depth 6|Set-Content -Encoding UTF8 -LiteralPath (Join-Path $agentic 'enforcement.json');$contextFiles+='enforcement.json'
}
$initial=@();Get-ChildItem $workspace -File -Recurse|Where-Object{$_.FullName -notmatch '[\\/]\.agentic[\\/]'}|ForEach-Object{$initial+=[ordered]@{path=$_.FullName.Substring($workspace.Length+1).Replace('\','/');sha256=(Get-FileHash $_.FullName -Algorithm SHA256).Hash}}
$prompt="Work only inside this benchmark workspace. Read task.md and repository documentation. Implement the task, run public tests, and leave the workspace in a final verified state. Do not search for hidden graders or external benchmark files."
if($Arm -ne 'vanilla'){$prompt+=" Follow the files in .agentic/ in addition to the fixture instructions."}
Set-Content -Encoding UTF8 -LiteralPath (Join-Path $runPath 'prompt.txt') -Value $prompt
$protectedInitial=@($initial|Where-Object{$_.path -eq $fixtureDef.task_file -or $_.path.StartsWith('tests/')})
$manifest=[ordered]@{schema_version=1;run_id=$runId;status='prepared';fixture=$Fixture;arm=$Arm;provider=$Provider;requested_model_profile=$ModelProfile;actual_model=$null;effort=$null;trial=$Trial;created_at=[datetimeoffset]::Now.ToString('o');isolation=$Isolation;publishable_hidden_result=($Isolation -in @('container','vm','dedicated-wsl'));workspace='workspace';central_hidden_grader=$fixtureDef.hidden_grader;agent_context_files=$contextFiles;initial_files=$initial;protected_initial_files=$protectedInitial;public_test=$fixtureDef.public_test;prompt_sha256=(Get-FileHash (Join-Path $runPath 'prompt.txt') -Algorithm SHA256).Hash}
$manifest|ConvertTo-Json -Depth 10|Set-Content -Encoding UTF8 -LiteralPath (Join-Path $runPath 'run-manifest.json')
[ordered]@{run_id=$runId;run_path=$runPath;workspace=$workspace;prompt=(Join-Path $runPath 'prompt.txt');publishable_hidden_result=$manifest.publishable_hidden_result}|ConvertTo-Json -Depth 5
