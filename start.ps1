$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (!(Test-Path .env)) { Copy-Item .env.example .env }
docker compose up --build -d
if ($LASTEXITCODE -ne 0) { throw 'Docker Compose failed. Check that Docker Desktop is running.' }
Write-Host 'RootLens: http://localhost:8080 — click Open workspace, then Start workload.'
