# Start Buruuj Tawarruq Engine (API + Portal)
# Usage: .\start.ps1

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

if (-not (Test-Path ".venv")) {
    Write-Host "Creating Python virtual environment..."
    python -m venv .venv
    .venv\Scripts\pip install -r requirements.txt -e .
}

if (-not (Test-Path ".env")) {
    Copy-Item .env.example .env
    Write-Host "Created .env from .env.example"
}

if (-not (Test-Path "portal\node_modules")) {
    Write-Host "Installing portal dependencies..."
    Set-Location portal
    npm install
    Set-Location $Root
}

Write-Host ""
Write-Host "Starting services..."
Write-Host "  API:    http://127.0.0.1:8000/docs"
Write-Host "  Portal: http://127.0.0.1:5173"
Write-Host ""
Write-Host "Press Ctrl+C in each window to stop."
Write-Host ""

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$Root'; .venv\Scripts\python -m tawarruq.cli serve --host 127.0.0.1 --port 8000 --reload"
Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$Root\portal'; npm run dev"

Write-Host "Both servers launched in separate windows."
