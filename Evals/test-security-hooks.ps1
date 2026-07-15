[CmdletBinding()]
param([string]$OutputPath)
$ErrorActionPreference='Stop';$root=Split-Path -Parent $PSScriptRoot;$results=@()
function Invoke-Hook([string]$script,[string]$payload){$old=$ErrorActionPreference;$ErrorActionPreference='Continue';$payload|powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root $script) 2>&1|Out-Null;$code=$LASTEXITCODE;$ErrorActionPreference=$old;return $code}
$block='Claude/hooks/block-dangerous-command.ps1'
$protect='Claude/hooks/protect-files.ps1'
$cases=@(
    # protect-files: reject cases must return exactly 2 (the only code the harness blocks on)
    @{id='protect-env';script=$protect;payload='{"tool_input":{"file_path":"C:/repo/.env"}}';reject=$true},
    @{id='protect-hidden';script=$protect;payload='{"tool_input":{"file_path":"C:/repo/Evals/hidden/grade.py"}}';reject=$true},
    @{id='protect-fixture-hidden';script=$protect;payload='{"tool_input":{"file_path":"C:/repo/Evals/fixtures/entity-parser/hidden/grade.py"}}';reject=$true},
    @{id='protect-stable-manifest';script=$protect;payload='{"tool_input":{"file_path":"C:/repo/Runtime/stable/manifest.json"}}';reject=$true},
    @{id='protect-core-runtime';script=$protect;payload='{"tool_input":{"file_path":"C:/repo/Core/runtime.md"}}';reject=$true},
    @{id='protect-bootstrap';script=$protect;payload='{"tool_input":{"file_path":"C:/repo/Claude/BOOTSTRAP.md"}}';reject=$true},
    @{id='allow-source';script=$protect;payload='{"tool_input":{"file_path":"C:/repo/src/app.py"}}';reject=$false},
    @{id='allow-candidate';script=$protect;payload='{"tool_input":{"file_path":"C:/repo/Research/candidate-packages/x/report.md"}}';reject=$false},
    @{id='invalid-payload-fails-closed';script=$protect;payload='not-json';reject=$true},
    # block-dangerous-command: destructive variants must all return exactly 2
    @{id='reject-hard-reset';script=$block;payload='{"tool_input":{"command":"git reset --hard HEAD"}}';reject=$true},
    @{id='reject-recursive-delete';script=$block;payload='{"tool_input":{"command":"Remove-Item C:/repo -Recurse -Force"}}';reject=$true},
    @{id='reject-recursive-delete-reversed';script=$block;payload='{"tool_input":{"command":"Remove-Item C:/repo -Force -Recurse"}}';reject=$true},
    @{id='reject-recursive-delete-abbrev';script=$block;payload='{"tool_input":{"command":"Remove-Item C:/repo -Rec -Fo"}}';reject=$true},
    @{id='reject-ri-alias';script=$block;payload='{"tool_input":{"command":"ri C:/repo -Recurse -Force"}}';reject=$true},
    @{id='reject-rm-fr';script=$block;payload='{"tool_input":{"command":"rm -fr /tmp/x"}}';reject=$true},
    @{id='reject-rm-r-f';script=$block;payload='{"tool_input":{"command":"rm -r -f ./src"}}';reject=$true},
    @{id='reject-rm-long';script=$block;payload='{"tool_input":{"command":"rm --recursive --force /data"}}';reject=$true},
    @{id='reject-force-with-lease';script=$block;payload='{"tool_input":{"command":"git push --force-with-lease origin main"}}';reject=$true},
    @{id='reject-plus-refspec';script=$block;payload='{"tool_input":{"command":"git push origin +main"}}';reject=$true},
    @{id='reject-git-clean';script=$block;payload='{"tool_input":{"command":"git clean -fdx"}}';reject=$true},
    @{id='allow-tests';script=$block;payload='{"tool_input":{"command":"python -m unittest"}}';reject=$false},
    @{id='allow-normal-rm';script=$block;payload='{"tool_input":{"command":"rm ./build.log"}}';reject=$false},
    @{id='allow-normal-push';script=$block;payload='{"tool_input":{"command":"git push origin main"}}';reject=$false},
    # Codex immutable-eval patch guard
    @{id='codex-hidden-patch';script='Codex/templates/protect-eval-files.ps1';payload='{"patch":"*** Evals/hidden/grade.py"}';reject=$true},
    @{id='codex-fixture-hidden-patch';script='Codex/templates/protect-eval-files.ps1';payload='{"patch":"*** Evals/fixtures/api-compatibility/hidden/grade.py"}';reject=$true}
)
# reject cases must block with exactly exit 2; allow cases must pass with exit 0.
foreach($c in $cases){$code=Invoke-Hook $c.script $c.payload;$results+=[pscustomobject]@{id=$c.id;exit_code=$code;expected=if($c.reject){2}else{0};passed=if($c.reject){$code -eq 2}else{$code -eq 0}}}
$failed=@($results|Where-Object{-not $_.passed}).Count;$report=[ordered]@{schema_version=2;run_at=[datetimeoffset]::Now.ToString('o');cases=$results.Count;passed=$results.Count-$failed;failed=$failed;results=$results}
if(-not $OutputPath){$OutputPath=Join-Path $root ("Evals/reports/{0}-security-hooks.json" -f (Get-Date -Format 'yyyy-MM-dd-HHmmss'))};$report|ConvertTo-Json -Depth 8|Set-Content -Encoding UTF8 $OutputPath;$report|ConvertTo-Json -Depth 8;if($failed){exit 1}
