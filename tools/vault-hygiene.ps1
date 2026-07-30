[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$RemainingArgs = @()
)
# Thin launcher for the report-only vault hygiene scan. All arguments pass
# straight through to awbp/vault_hygiene.py (see --help there).
# The scan NEVER modifies repository content; it writes a dated JSON+MD report.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Get-Command python -ErrorAction SilentlyContinue
$prefix = @()
if ($python) {
    $pythonExe = $python.Source
} else {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if (-not $py) { throw "vault-hygiene needs a Python 3 interpreter ('python' or the Windows 'py' launcher) on PATH; none was found." }
    $pythonExe = $py.Source
    $prefix = @('-3')
}
& $pythonExe @prefix (Join-Path $root 'awbp/vault_hygiene.py') @RemainingArgs
exit $LASTEXITCODE
