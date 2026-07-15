[CmdletBinding()]
param([string]$Root)

$ErrorActionPreference = 'Stop'
if (-not $Root) { $Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot) }
$rootPath = (Resolve-Path -LiteralPath $Root).Path
$raw = & git -C $rootPath ls-files --cached --others --exclude-standard
if ($LASTEXITCODE -ne 0) { throw 'git ls-files failed.' }
$files = @($raw | Where-Object { $_ })
$findings = @()
$textExtensions = @('.md', '.txt', '.json', '.jsonl', '.ps1', '.sh', '.py', '.js', '.ts', '.toml', '.yaml', '.yml', '.xml', '.csv')
$credentialName = '(^|/)(auth\.json|\.credentials\.json|\.claude\.json)$'
$secretPatterns = @(
    'sk-ant-[A-Za-z0-9_-]{20,}',
    'sk-proj-[A-Za-z0-9_-]{20,}',
    '"(?:accessToken|refreshToken)"\s*:\s*"[^"\r\n]{20,}"'
)

foreach ($relative in $files) {
    $normalized = $relative.Replace('\', '/')
    if ($normalized -match $credentialName) {
        $findings += [ordered]@{ path = $normalized; reason = 'credential-filename' }
        continue
    }
    $extension = [IO.Path]::GetExtension($relative).ToLowerInvariant()
    if ($extension -notin $textExtensions) { continue }
    $path = Join-Path $rootPath $relative
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { continue }
    $content = Get-Content -Raw -Encoding UTF8 -LiteralPath $path
    foreach ($pattern in $secretPatterns) {
        if ($content -match $pattern) {
            $findings += [ordered]@{ path = $normalized; reason = 'credential-shaped-content' }
            break
        }
    }
}

$report = [ordered]@{
    schema_version = 1
    cases = $files.Count
    passed = $files.Count - $findings.Count
    failed = $findings.Count
    findings = $findings
}
$report | ConvertTo-Json -Depth 6
if ($findings.Count) { exit 1 }
