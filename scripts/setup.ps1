param([switch]$SkipBuild)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)

function New-Secret {
    $bytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    return ([BitConverter]::ToString($bytes)).Replace('-', '').ToLowerInvariant()
}

if (-not (Test-Path -LiteralPath '.env.open-webui')) {
    Set-Content -LiteralPath '.env.open-webui' -Value ('WEBUI_SECRET_KEY=' + (New-Secret)) -Encoding ascii
}
if (-not (Test-Path -LiteralPath '.env.drawing')) {
    @(('DRAWING_API_KEY=' + (New-Secret)), 'DRAWING_PUBLIC_URL=http://localhost:8001') | Set-Content -LiteralPath '.env.drawing' -Encoding ascii
}
if ($SkipBuild) { docker compose up -d --wait --wait-timeout 240 }
else { docker compose up -d --build --wait --wait-timeout 240 }
if ($LASTEXITCODE -ne 0) { throw 'Docker services failed to start' }

Get-Content -Raw scripts/register_tool.py | docker compose exec -T open-webui python -
if ($LASTEXITCODE -ne 0) { throw 'Tool registration failed' }
docker compose restart open-webui
if ($LASTEXITCODE -ne 0) { throw 'Open WebUI restart failed' }
docker compose up -d --wait --wait-timeout 240
if ($LASTEXITCODE -ne 0) { throw 'Open WebUI did not become healthy' }
Write-Host 'Ready: http://localhost:3000 - enable Drawing Studio in the chat Tools menu.'
