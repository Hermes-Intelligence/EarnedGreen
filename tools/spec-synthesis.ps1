[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$RemainingArgs = @()
)
# Thin launcher for the spec-first planning tool. All arguments pass straight
# through to awbp/spec_synthesis.py (subcommands: compile, validate).
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Get-Command python -ErrorAction SilentlyContinue
$prefix = @()
if ($python) {
    $pythonExe = $python.Source
} else {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if (-not $py) { throw "spec-synthesis needs a Python 3 interpreter ('python' or the Windows 'py' launcher) on PATH; none was found." }
    $pythonExe = $py.Source
    $prefix = @('-3')
}
& $pythonExe @prefix (Join-Path $root 'awbp/spec_synthesis.py') @RemainingArgs
exit $LASTEXITCODE
