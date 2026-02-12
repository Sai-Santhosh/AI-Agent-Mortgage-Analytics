# AI-Financer Startup Script (PowerShell)
# Run: .\scripts\run_all.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

Write-Host "AI-Financer Setup" -ForegroundColor Cyan
Write-Host "=================" -ForegroundColor Cyan

if (-not (Test-Path "data\analytics.db")) {
    Write-Host "Initializing database..." -ForegroundColor Yellow
    python scripts/init_db.py
    Write-Host "Ingesting data (CFPB, FRED, FHFA)..." -ForegroundColor Yellow
    python scripts/ingest_data.py
}

Write-Host "`nStart the API: python run.py" -ForegroundColor Green
Write-Host "Start the UI:  cd frontend && npm run dev" -ForegroundColor Green
Write-Host "`nAPI: http://localhost:8000 | UI: http://localhost:5173" -ForegroundColor Gray
