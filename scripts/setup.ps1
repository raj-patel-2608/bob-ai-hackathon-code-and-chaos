# One-time setup (Windows PowerShell). Creates a virtual environment per Python service and installs the frontend.
# Usage:  powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$src = Join-Path $repo "src"

function New-Venv($dir) {
    Write-Host "`n== $dir" -ForegroundColor Cyan
    Push-Location (Join-Path $src $dir)
    if (-not (Test-Path ".venv")) { python -m venv .venv }
    .\.venv\Scripts\python.exe -m pip install --upgrade pip | Out-Null
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    Pop-Location
}

New-Venv "core_api"
New-Venv "model_service"        # ~3 GB: PyTorch (CUDA build, also runs on CPU) + transformers
New-Venv "mcp_server"

Write-Host "`n== frontend" -ForegroundColor Cyan
Push-Location (Join-Path $src "frontend")
npm install
if (-not (Test-Path ".env.local")) { Copy-Item ".env.local.example" ".env.local" }
Pop-Location

if (-not (Test-Path (Join-Path $src ".env"))) {
    Copy-Item (Join-Path $src ".env.example") (Join-Path $src ".env")
    Write-Host "`nCreated src\.env from src\.env.example - add your watsonx credentials (optional)." -ForegroundColor Yellow
}
Write-Host "`nSetup complete. Next: scripts\start_all.ps1" -ForegroundColor Green
