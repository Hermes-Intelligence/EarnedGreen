[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$Run, [Parameter(Mandatory=$true)][string]$ProviderId, [string]$ConfigPath, [switch]$Execute, [string]$Root)
$ErrorActionPreference='Stop'
if(-not $Root){$Root=Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))}
$rootPath=(Resolve-Path $Root).Path;if(-not $ConfigPath){$ConfigPath=Join-Path $rootPath 'Evals/local/provider-settings.json'}
if(-not(Test-Path $ConfigPath)){throw "Local provider config missing. Copy Evals/adapters/providers/provider-settings.example.json to Evals/local/provider-settings.json and verify flags against the installed CLI."}
$config=Get-Content -Raw -Encoding UTF8 $ConfigPath|ConvertFrom-Json;$provider=@($config.providers|Where-Object id -eq $ProviderId)[0];if(-not $provider){throw "Unknown local provider: $ProviderId"}
$runPath=if([IO.Path]::IsPathRooted($Run)){(Resolve-Path $Run).Path}else{(Resolve-Path (Join-Path $rootPath "Evals/runs/$Run")).Path};$m=Get-Content -Raw (Join-Path $runPath 'run-manifest.json')|ConvertFrom-Json
$workspace=Join-Path $runPath $m.workspace;$prompt=Join-Path $runPath 'prompt.txt';$exe=(Get-Command $provider.executable -ErrorAction Stop).Source
$args=@($provider.arguments|ForEach-Object{([string]$_).Replace('{workspace}',$workspace).Replace('{prompt_file}',$prompt).Replace('{model_profile}',[string]$m.requested_model_profile)})
$preview=[ordered]@{schema_version=1;provider=$ProviderId;executable=$exe;arguments=$args;execute=[bool]$Execute;warning='Arguments are local configuration and must be verified against the installed CLI. Secrets must come from environment variables.'}
if(-not $Execute){$preview|ConvertTo-Json -Depth 6;exit 3}
$started=[datetimeoffset]::Now;$output=& $exe @args 2>&1|Out-String;$exit=$LASTEXITCODE;$finished=[datetimeoffset]::Now
[ordered]@{schema_version=1;provider=$ProviderId;started_at=$started.ToString('o');finished_at=$finished.ToString('o');exit_code=$exit;output=$output}|ConvertTo-Json -Depth 6|Set-Content -Encoding UTF8 (Join-Path $runPath 'provider-execution.json')
Get-Content -Raw (Join-Path $runPath 'provider-execution.json');exit $exit
