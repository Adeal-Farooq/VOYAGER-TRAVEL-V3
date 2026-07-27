# VOYAGER - Start local dev servers
# Usage: .\start.ps1               (normal mode)
#        .\start.ps1 -TestTime     (12:00 PM frozen time)

param([switch]$TestTime)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path

# Kill any existing servers
Stop-Process -Name "python" -Force -ErrorAction SilentlyContinue
Stop-Process -Name "node" -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# Start backend
$beCmd = "cd '$root'; "
if ($TestTime) { $beCmd += "`$env:VOYAGER_TEST_TIME='2024-07-15 12:00:00'; " }
$beCmd += "python -m uvicorn backend.main:app --reload --port 8000"
Start-Process powershell -ArgumentList "-NoExit -Command $beCmd" -WindowStyle Minimized

# Start frontend
$feCmd = "cd '$root\frontend'; npx vite --port 3000 --host"
Start-Process powershell -ArgumentList "-NoExit -Command $feCmd" -WindowStyle Minimized

Write-Host "`n=========================================" -ForegroundColor Cyan
Write-Host "  VOYAGER starting..." -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host " Frontend: http://localhost:3000" -ForegroundColor Green
Write-Host " Backend:  http://localhost:8000" -ForegroundColor Green
Write-Host " Docs:     http://localhost:8000/docs" -ForegroundColor Green
if ($TestTime) { Write-Host " Time:     Frozen at 2024-07-15 12:00 PM" -ForegroundColor Yellow }
Write-Host "=========================================`n"
