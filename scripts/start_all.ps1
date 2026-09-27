# Starts the whole CrimeFIR system with one command (Windows) and waits until it is live.
#   model service  http://127.0.0.1:8100   Laya + Granite Embedding (local GPU/CPU), Granite LLM via watsonx.ai
#   core API       http://127.0.0.1:8000   REST API + background worker (docs at /docs)
#   frontend       http://localhost:3000   the web app
# Each service opens in its own window (close a window to stop that service, or run scripts\stop_all.ps1).
#
#   powershell -ExecutionPolicy Bypass -File scripts\start_all.ps1              # asks before loading sample data
#   powershell -ExecutionPolicy Bypass -File scripts\start_all.ps1 -LoadSample  # also load the 400 sample FIRs if empty
#   powershell -ExecutionPolicy Bypass -File scripts\start_all.ps1 -NoBrowser
param([switch]$LoadSample, [switch]$NoBrowser, [switch]$Yes)

$repo = Split-Path -Parent $PSScriptRoot
$src = Join-Path $repo "src"
New-Item -ItemType Directory -Force (Join-Path $repo "var\logs") | Out-Null

function Listening($port) { return [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) }
function Up($url) { try { Invoke-WebRequest $url -UseBasicParsing -TimeoutSec 3 | Out-Null; return $true } catch { return $false } }

# ------------------------------------------------------------------ installed?
$missing = @()
foreach ($svc in @("model_service", "core_api")) { if (-not (Test-Path (Join-Path $src "$svc\.venv\Scripts\python.exe"))) { $missing += $svc } }
if (-not (Test-Path (Join-Path $src "frontend\node_modules"))) { $missing += "frontend" }
if ($missing) {
    Write-Host "Not installed yet: $($missing -join ', '). Run first:  powershell -ExecutionPolicy Bypass -File scripts\setup.ps1" -ForegroundColor Yellow
    exit 1
}

# ------------------------------------------------------------------ start (skips services that are already running)
$services = @(
    @{ Name = "model service"; Dir = "model_service"; Port = 8100; Health = "http://127.0.0.1:8100/v1/health"; Wait = 600
       Cmd = "`$env:HF_HUB_DISABLE_SYMLINKS_WARNING='1'; .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8100" },
    @{ Name = "core API"; Dir = "core_api"; Port = 8000; Health = "http://127.0.0.1:8000/api/health/live"; Wait = 120
       Cmd = ".\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000" },
    @{ Name = "frontend"; Dir = "frontend"; Port = 3000; Health = "http://localhost:3000/"; Wait = 180
       Cmd = "npm run dev" }
)
foreach ($s in $services) {
    if (Listening $s.Port) { Write-Host ("  {0,-14} already running on port {1}" -f $s.Name, $s.Port) -ForegroundColor DarkGray; continue }
    $full = "`$Host.UI.RawUI.WindowTitle = 'CrimeFIR $($s.Name) :$($s.Port)'; `$env:PYTHONIOENCODING='utf-8'; Set-Location '$(Join-Path $src $s.Dir)'; $($s.Cmd)"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $full | Out-Null
    Write-Host ("  {0,-14} starting on port {1} (own window)" -f $s.Name, $s.Port)
}

# ------------------------------------------------------------------ wait until live
Write-Host "`nWaiting for the services (first start downloads the AI models if setup did not; later starts take ~20-60 s)..."
foreach ($s in $services) {
    $t0 = Get-Date
    Write-Host -NoNewline ("  {0,-14} " -f $s.Name)
    while (-not (Up $s.Health)) {
        if (((Get-Date) - $t0).TotalSeconds -gt $s.Wait) {
            Write-Host " not responding after $($s.Wait) s - check its window for errors." -ForegroundColor Red
            exit 1
        }
        Write-Host -NoNewline "."
        Start-Sleep -Seconds 3
    }
    Write-Host (" live ({0:N0} s)" -f ((Get-Date) - $t0).TotalSeconds) -ForegroundColor Green
}
try {
    $ready = Invoke-RestMethod "http://127.0.0.1:8000/api/health/ready" -TimeoutSec 10
    $caps = $ready.checks.model_service.capabilities
    Write-Host "`n  Mode: $($ready.mode)"
    foreach ($k in @("decision", "embedding", "generator")) {
        $c = $caps.$k
        if ($c.available) { Write-Host ("  {0,-10} {1} on {2}" -f $k, $c.model_id, $c.device) -ForegroundColor Green }
        else { Write-Host ("  {0,-10} not available: {1}" -f $k, $c.reason) -ForegroundColor Yellow }
    }
} catch { Write-Host "  (could not read the readiness details)" -ForegroundColor Yellow }

# ------------------------------------------------------------------ sample data (only if the database is empty)
try { $dash = Invoke-RestMethod "http://127.0.0.1:8000/api/dashboard" -TimeoutSec 10 } catch { $dash = $null }
if ($dash -and $dash.total_firs -eq 0) {
    $load = $LoadSample
    if (-not $load -and -not $Yes) {
        $a = Read-Host "`n  The database is empty. Load the 400 sample FIRs now (about 6-10 minutes of processing)? [Y/n]"
        $load = [string]::IsNullOrWhiteSpace($a) -or $a.Trim() -match '^(y|yes)$'
    }
    if ($load) {
        $raw = curl.exe -s -F "file=@$(Join-Path $src 'dataset\firs_main.txt')" "http://127.0.0.1:8000/api/batches"
        $acc = $raw | ConvertFrom-Json
        Write-Host "  Uploaded: $($acc.created) FIRs. Processing continues in the background; follow it on the Add FIRs page." -ForegroundColor Green
    } else { Write-Host "  OK - add FIRs later on the Add FIRs page (sample files are in src\dataset\)." }
} elseif ($dash) { Write-Host "`n  Database: $($dash.total_firs) FIRs, $($dash.flagged_clusters) repeat-offender groups." }

Write-Host "`nCrimeFIR is live:  http://localhost:3000   (API docs: http://127.0.0.1:8000/docs)" -ForegroundColor Green
Write-Host "Stop everything:   powershell -ExecutionPolicy Bypass -File scripts\stop_all.ps1"
if (-not $NoBrowser) { Start-Process "http://localhost:3000$(if ($dash -and $dash.total_firs -eq 0) { '/upload' } else { '' })" }
