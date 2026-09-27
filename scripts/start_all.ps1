# Starts the three CrimeFIR services, each in its own PowerShell window (Windows).
#   model service  http://127.0.0.1:8100   (Laya + Granite Embedding locally, Granite LLM on watsonx.ai)
#   core API       http://127.0.0.1:8000   (docs at /docs)
#   frontend       http://localhost:3000
# Usage:  powershell -ExecutionPolicy Bypass -File scripts\start_all.ps1
$repo = Split-Path -Parent $PSScriptRoot
$src = Join-Path $repo "src"
New-Item -ItemType Directory -Force (Join-Path $repo "var\logs") | Out-Null

function Start-CrimeFir($title, $dir, $command) {
    $full = "`$Host.UI.RawUI.WindowTitle = '$title'; Set-Location '$(Join-Path $src $dir)'; $command"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $full
}

Start-CrimeFir "CrimeFIR model service :8100" "model_service" `
    ".\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8100"
Start-CrimeFir "CrimeFIR core API :8000" "core_api" `
    ".\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
Start-CrimeFir "CrimeFIR frontend :3000" "frontend" "npm run dev"

Write-Host "Starting... the model service needs ~20-60 s to load the models (first run downloads them)."
Write-Host "Then open http://localhost:3000 and load data with scripts\load_dataset.ps1"
