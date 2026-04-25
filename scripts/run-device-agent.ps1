$ErrorActionPreference = 'Stop'

$envNames = @(
    'CODI_CENTER_URL',
    'CODI_DEVICE_API_TOKEN',
    'CODI_DEVICE_ID',
    'CODI_DEVICE_LABEL',
    'CODI_DEVICE_TYPE',
    'CODI_DEVICE_CAPABILITIES',
    'CODI_DEVICE_HEARTBEAT_INTERVAL',
    'CODI_DEVICE_TASK_POLL_INTERVAL',
    'CODI_BUSINESS_DATABASE_PATHS'
)

foreach ($name in $envNames) {
    $value = [Environment]::GetEnvironmentVariable($name, 'User')
    if ($value) {
        Set-Item -Path "Env:$name" -Value $value
    }
}

$capabilityMap = @{}
$rawCapabilities = $env:CODI_DEVICE_CAPABILITIES
if (-not $rawCapabilities) {
    $rawCapabilities = ''
}
foreach ($item in ($rawCapabilities -split ',')) {
    $normalized = $item.Trim().ToLowerInvariant()
    if ($normalized) {
        $capabilityMap[$normalized] = $true
    }
}
$capabilityMap['natural_query'] = $true
if ($capabilityMap.Count -gt 0) {
    $env:CODI_DEVICE_CAPABILITIES = (($capabilityMap.Keys | Sort-Object) -join ',')
}

$repo = 'C:\ai-agent-telegram'
$logDir = Join-Path $repo 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
Set-Location $repo

while ($true) {
    .\.venv\Scripts\python.exe -m agent.main
    $message = '[{0}] agent exited with code {1}; retrying in 10s' -f (Get-Date -Format s), $LASTEXITCODE
    Add-Content -LiteralPath (Join-Path $logDir 'agent-runner.log') -Value $message
    Start-Sleep -Seconds 10
}
