[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$EventsPath,
    [Parameter(Mandatory=$true)][ValidateSet('codex','claude')][string]$Provider
)
$ErrorActionPreference='Stop'
$resolved=(Resolve-Path -LiteralPath $EventsPath).Path
$actualModel=$null
$usage=[ordered]@{input_tokens=0;cached_input_tokens=0;cache_creation_input_tokens=0;cache_read_input_tokens=0;output_tokens=0;reasoning_output_tokens=0;total_observed_tokens=0;accounting='not-reported';source='not-reported'}
$reportedCostUsd=$null
foreach($line in Get-Content -LiteralPath $resolved -Encoding UTF8){
    try{
        $event=$line|ConvertFrom-Json
        $candidate=if($event.PSObject.Properties.Name -contains 'model'){[string]$event.model}elseif($event.message -and $event.message.PSObject.Properties.Name -contains 'model'){[string]$event.message.model}else{$null}
        if($candidate -and -not $actualModel){$actualModel=($candidate -replace '\x1b\[[0-9;]*[A-Za-z]','' -replace '\[[0-9;]*m\]?','').Trim()}
        if($Provider -eq 'codex' -and $event.type -eq 'turn.completed' -and $event.usage){
            $usage.input_tokens=[long]$event.usage.input_tokens
            $usage.cached_input_tokens=[long]$event.usage.cached_input_tokens
            $usage.output_tokens=[long]$event.usage.output_tokens
            $usage.reasoning_output_tokens=[long]$event.usage.reasoning_output_tokens
            $usage.total_observed_tokens=$usage.input_tokens+$usage.output_tokens
            $usage.accounting='input-includes-cached; total=input+output'
            $usage.source='codex-turn-completed'
        }
        if($Provider -eq 'claude' -and $event.type -eq 'result' -and $event.usage){
            $usage.input_tokens=[long]$event.usage.input_tokens
            $usage.cache_creation_input_tokens=[long]$event.usage.cache_creation_input_tokens
            $usage.cache_read_input_tokens=[long]$event.usage.cache_read_input_tokens
            $usage.output_tokens=[long]$event.usage.output_tokens
            $usage.total_observed_tokens=$usage.input_tokens+$usage.cache_creation_input_tokens+$usage.cache_read_input_tokens+$usage.output_tokens
            $usage.accounting='total=input+cache_creation+cache_read+output'
            $usage.source='claude-result'
            if($event.PSObject.Properties.Name -contains 'total_cost_usd'){$reportedCostUsd=[double]$event.total_cost_usd}
        }
    }catch{}
}
[ordered]@{schema_version=1;provider=$Provider;actual_model=$actualModel;token_usage=$usage;monetary_cost=[ordered]@{amount_usd=$reportedCostUsd;basis=if($null -ne $reportedCostUsd){'provider-reported-usd; subscription charge may differ'}else{'not-reported-by-subscription-cli'}}}|ConvertTo-Json -Depth 8
