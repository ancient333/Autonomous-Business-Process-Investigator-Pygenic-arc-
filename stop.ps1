Set-Location $PSScriptRoot
try { Invoke-RestMethod http://localhost:8080/api/control -Method Post -ContentType application/json -Body '{"action":"stop"}' } catch { Write-Host 'API unavailable; stopping containers.' }
docker compose down
Write-Host 'Stopped. PostgreSQL volume retained.'
