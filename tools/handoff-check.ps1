[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$HandoffPath, [int]$MaxAgeHours=168)
$ErrorActionPreference="Stop"
$h=Get-Content -Raw -Encoding UTF8 -LiteralPath $HandoffPath|ConvertFrom-Json
$missing=@()
foreach($name in @('schema_version','objective_id','task','status','updated_at','decisions','evidence','blockers','next_action','changed_paths')){if($null -eq $h.$name){$missing+=$name}}
$duplicateDecisions=@($h.decisions.id|Group-Object|Where-Object Count -gt 1|ForEach-Object Name)
$age=([datetimeoffset]::Now-[datetimeoffset]$h.updated_at).TotalHours
$errors=@()
if($missing.Count){$errors+="missing fields: $($missing -join ', ')"}
if(-not $h.next_action -or $h.next_action.Length -lt 5){$errors+="next_action is not actionable"}
if($duplicateDecisions.Count){$errors+="duplicate decision IDs: $($duplicateDecisions -join ', ')"}
if($age -gt $MaxAgeHours -and $h.status -in @('in_progress','blocked','awaiting_review')){$errors+="handoff is stale ($([math]::Round($age,1)) hours)"}
if($h.status -eq 'complete' -and @($h.requirements|Where-Object{$_.status -notin @('verified','not_applicable','rejected')}).Count){$errors+="complete handoff contains incomplete requirements"}
$result=[ordered]@{schema_version=1;valid=($errors.Count -eq 0);path=(Resolve-Path $HandoffPath).Path;age_hours=[math]::Round($age,2);errors=$errors;next_action=$h.next_action}
$result|ConvertTo-Json -Depth 6
if($errors.Count){exit 2}
