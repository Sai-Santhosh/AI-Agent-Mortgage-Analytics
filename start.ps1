# AI-Financer Startup Script
# Usage: .\start.ps1

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

# Ensure venv exists
if (-not (Test-Path ".venv")) {
    Write-Host "Creating venv..." -ForegroundColor Yellow
    python -m venv .venv
}

# Activate and ensure minimal deps
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
$venvPip = Join-Path $root ".venv\Scripts\pip.exe"

Write-Host "Checking dependencies..." -ForegroundColor Cyan
& $venvPip install -q fastapi uvicorn python-multipart sqlalchemy pandas python-dotenv pydantic pydantic-settings httpx fredapi 2>$null

# Ensure DB exists
if (-not (Test-Path "data\analytics.db")) {
    Write-Host "Initializing database..." -ForegroundColor Yellow
    & $venvPython scripts/init_db.py 2>$null
    Write-Host "Ingesting data..." -ForegroundColor Yellow
    & $venvPython scripts/ingest_data.py 2>$null
}

# Install langchain if missing (for LLM)
& $venvPip install -q langchain langchain-openai langchain-community 2>$null

$port = 8001
Write-Host "`nStarting API on http://localhost:$port" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop`n" -ForegroundColor Gray
& $venvPython -m uvicorn app.main:app --host 0.0.0.0 --port $port --reload
