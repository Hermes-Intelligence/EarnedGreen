<#
.SYNOPSIS
  Thin PowerShell shim over awbp.py.

.DESCRIPTION
  The behaviour lives in awbp.py, because the same commands must work in Claude
  on Windows and in Codex under WSL, and two implementations of one tool is two
  places for them to disagree. This file only finds Python and forwards.

.EXAMPLE
  powershell -File <awbp>/awbp.ps1 init
  powershell -File <awbp>/awbp.ps1 task "add pagination to the exposure export"
#>
[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Arguments
)

$ErrorActionPreference = "Stop"

function Get-Python {
    foreach ($name in @("python", "python3", "py")) {
        $found = Get-Command $name -ErrorAction SilentlyContinue
        if ($found) { return $found.Source }
    }
    throw "Python is required and was not found on PATH."
}

& (Get-Python) (Join-Path $PSScriptRoot "awbp.py") @Arguments
exit $LASTEXITCODE
