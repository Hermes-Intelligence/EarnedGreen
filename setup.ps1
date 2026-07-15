[CmdletBinding()]
param([switch]$InstallCodex,[switch]$LoginCodex,[switch]$GlobalPointers,[switch]$SkipSelfTest)
& (Join-Path $PSScriptRoot 'Setup/bootstrap/setup.ps1') -InstallCodex:$InstallCodex -LoginCodex:$LoginCodex -GlobalPointers:$GlobalPointers -SkipSelfTest:$SkipSelfTest
exit $LASTEXITCODE
