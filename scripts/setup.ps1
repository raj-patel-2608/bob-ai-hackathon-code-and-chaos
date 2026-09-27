# CrimeFIR interactive setup (Windows PowerShell 5.1+). Checks everything first and asks before installing anything.
#
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1          # interactive (Y/n questions)
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1 -Yes     # answer "yes" to everything (unattended)
#
# Steps: 1 prerequisites (Python, Node.js, GPU)  2 Python packages (3 services)  3 frontend packages
#        4 AI models (Laya, Granite Embedding)   5 configuration + IBM watsonx.ai  6 tests (optional)  7 start
# Safe to run again at any time: things that are already in place are only checked, never reinstalled.
param([switch]$Yes, [switch]$NoStart)

$ErrorActionPreference = "Continue"          # native tools (pip, npm) report through exit codes, checked below
$repo = Split-Path -Parent $PSScriptRoot
$src = Join-Path $repo "src"
$doctor = Join-Path $PSScriptRoot "doctor.py"
$env:PYTHONIOENCODING = "utf-8"
$env:HF_HUB_DISABLE_SYMLINKS_WARNING = "1"
$summary = [ordered]@{}

function Step($n, $title) { Write-Host ""; Write-Host "[$n/7] $title" -ForegroundColor Cyan }
function Ok($m) { Write-Host "  OK       $m" -ForegroundColor Green }
function Miss($m) { Write-Host "  MISSING  $m" -ForegroundColor Yellow }
function Fail($m) { Write-Host "  FAIL     $m" -ForegroundColor Red }
function Info($m) { Write-Host "           $m" -ForegroundColor Gray }
function Ask([string]$q, [bool]$default = $true) {
    if ($Yes) { Write-Host "  $q -> yes (-Yes)" -ForegroundColor DarkGray; return $true }
    $hint = if ($default) { "[Y/n]" } else { "[y/N]" }
    while ($true) {
        $a = Read-Host "  $q $hint"
        if ([string]::IsNullOrWhiteSpace($a)) { return $default }
        if ($a.Trim() -match '^(y|yes)$') { return $true }
        if ($a.Trim() -match '^(n|no)$') { return $false }
        Write-Host "  Please answer y or n."
    }
}
function Has($cmd) { return [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }
function Winget-Install($id, $label) {
    if (-not (Has "winget")) { Info "Install $label manually, then run this script again."; return }
    if (Ask "Install $label now with winget?" $true) {
        winget install -e --id $id --accept-source-agreements --accept-package-agreements
        Write-Host "  Close this window, open a new PowerShell (so PATH is refreshed) and run setup.ps1 again." -ForegroundColor Yellow
        exit 0
    }
}

Write-Host "CrimeFIR setup  -  repo: $repo" -ForegroundColor White
Write-Host "Nothing is installed without asking. Press Enter to accept the default shown in capitals." -ForegroundColor DarkGray

# ------------------------------------------------------------------------------------------------ 1 prerequisites
Step 1 "Prerequisites"
$PyExe = $null; $PyArgs = @()
foreach ($spec in @("py -3.12", "py -3.11", "python", "python3")) {
    $parts = $spec -split " "
    $exe = $parts[0]; $exeArgs = @($parts | Select-Object -Skip 1)
    if (-not (Has $exe)) { continue }
    $ver = & $exe @exeArgs -c "import sys;print('%d.%d' % sys.version_info[:2])" 2>$null
    if ($LASTEXITCODE -eq 0 -and $ver -and [version]$ver -ge [version]"3.11") { $PyExe = $exe; $PyArgs = $exeArgs; break }
}
if ($PyExe) { Ok "Python $ver ($PyExe $PyArgs)" } else {
    Miss "Python 3.11 or newer (3.12 recommended)"
    Winget-Install "Python.Python.3.12" "Python 3.12"
    exit 1
}
if (Has "node") {
    $nodeVer = (node -v).TrimStart("v")
    if ([version]$nodeVer -ge [version]"20.9") { Ok "Node.js $nodeVer, npm $(npm -v)" } else {
        Miss "Node.js 20.9+ (found $nodeVer)"; Winget-Install "OpenJS.NodeJS.LTS" "Node.js LTS"; exit 1
    }
} else { Miss "Node.js 20.9+"; Winget-Install "OpenJS.NodeJS.LTS" "Node.js LTS"; exit 1 }
$gpu = $false
if (Has "nvidia-smi") {
    $g = nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>$null
    if ($LASTEXITCODE -eq 0 -and $g) { $gpu = $true; Ok "NVIDIA GPU: $g (models run on the GPU)" }
}
if (-not $gpu) { Info "No NVIDIA GPU found: the AI models will run on the CPU (slower, but everything works)." }
$free = [math]::Round((Get-PSDrive -Name ($repo.Substring(0, 1))).Free / 1GB, 1)
if ($free -lt 8) { Miss "only $free GB free disk space (about 8-12 GB is needed)" } else { Ok "$free GB free disk space" }
$summary["Prerequisites"] = "OK"

# ------------------------------------------------------------------------------------------------ 2 python packages
Step 2 "Python packages (core API, model service, MCP server for IBM Bob)"
$sizes = @{ core_api = "~60 MB"; model_service = $(if ($gpu) { "~3.5 GB, PyTorch with CUDA" } else { "~3.5 GB, or ~1 GB with CPU-only PyTorch" }); mcp_server = "~30 MB" }

# (native output goes to Out-Host: inside a function it would otherwise become part of the return value)
function Install-Requirements($svc, $dir, $venvPy) {
    & $venvPy -m pip install --upgrade pip --quiet | Out-Host
    $req = Join-Path $dir "requirements.txt"
    if ($svc -eq "model_service" -and -not $gpu -and (Ask "No NVIDIA GPU: install the smaller CPU-only PyTorch instead of the CUDA build?" $true)) {
        $torchLine = (Get-Content $req | Where-Object { $_ -match '^torch==' }) -replace '\+.*$', ''
        & $venvPy -m pip install $torchLine --index-url https://download.pytorch.org/whl/cpu | Out-Host
        if ($LASTEXITCODE -ne 0) { return $false }
        $rest = Join-Path $env:TEMP "crimefir-model-service-reqs.txt"
        Get-Content $req | Where-Object { $_ -notmatch '^(torch==|--extra-index-url)' } | Set-Content $rest
        $req = $rest
    }
    & $venvPy -m pip install -r $req | Out-Host
    return ($LASTEXITCODE -eq 0)
}

foreach ($svc in @("core_api", "model_service", "mcp_server")) {
    $dir = Join-Path $src $svc
    $venvPy = Join-Path $dir ".venv\Scripts\python.exe"
    Write-Host "  - $svc" -ForegroundColor White
    if (-not (Test-Path $venvPy)) {
        Miss "no virtual environment in src\$svc\.venv"
        if (-not (Ask "Create it and install the $svc packages ($($sizes[$svc]))?" $true)) { $summary[$svc] = "skipped"; continue }
        & $PyExe @PyArgs -m venv (Join-Path $dir ".venv")
        if ($LASTEXITCODE -ne 0) { Fail "could not create the virtual environment"; $summary[$svc] = "FAILED"; continue }
    } else {
        $out = & $venvPy $doctor reqs (Join-Path $dir "requirements.txt")
        if ($LASTEXITCODE -eq 0) { Ok "all packages installed"; $summary[$svc] = "OK"; continue }
        $out | ForEach-Object { Info $_ }
        if (-not (Ask "Install / update these packages?" $true)) { $summary[$svc] = "incomplete (skipped)"; continue }
    }
    if (Install-Requirements $svc $dir $venvPy) { Ok "$svc packages installed"; $summary[$svc] = "OK" }
    else { Fail "pip install failed for $svc (see the messages above)"; $summary[$svc] = "FAILED" }
}

# ------------------------------------------------------------------------------------------------ 3 frontend
Step 3 "Frontend packages (Next.js)"
$fe = Join-Path $src "frontend"
Push-Location $fe
$feOk = $false
if (Test-Path "node_modules") {
    npm ls --depth=0 --silent *> $null
    $feOk = ($LASTEXITCODE -eq 0)
}
if ($feOk) { Ok "node_modules up to date"; $summary["frontend"] = "OK" } else {
    Miss "frontend packages not installed or out of date"
    if (Ask "Install them now (npm ci, ~400 MB)?" $true) {
        if (Test-Path "package-lock.json") { npm ci } else { npm install }
        if ($LASTEXITCODE -eq 0) { Ok "frontend packages installed"; $summary["frontend"] = "OK" } else { Fail "npm failed"; $summary["frontend"] = "FAILED" }
    } else { $summary["frontend"] = "skipped" }
}
if (-not (Test-Path ".env.local")) { Copy-Item ".env.local.example" ".env.local"; Ok "created src\frontend\.env.local (API at http://localhost:8000)" }
Pop-Location

# ------------------------------------------------------------------------------------------------ 4 models
Step 4 "AI models"
$msPy = Join-Path $src "model_service\.venv\Scripts\python.exe"
if (-not (Test-Path $msPy) -or $summary["model_service"] -ne "OK") {
    Miss "model service packages are not installed, so the models cannot be checked (run setup again after step 2)"
    $summary["models"] = "not checked"
} else {
    & $msPy $doctor gpu | Out-Host
    & $msPy $doctor models | Out-Host
    if ($LASTEXITCODE -eq 0) { $summary["models"] = "OK" } else {
        Info "Without them the model service downloads them on its first start instead (slower first start)."
        if (Ask "Download the missing models now (Laya ~1.7 GB, Granite Embedding ~65 MB)?" $true) {
            & $msPy $doctor models --download | Out-Host
            $summary["models"] = $(if ($LASTEXITCODE -eq 0) { "OK" } else { "FAILED (check internet access to huggingface.co)" })
        } else { $summary["models"] = "download on first start" }
    }
}

# ------------------------------------------------------------------------------------------------ 5 configuration
Step 5 "Configuration and IBM watsonx.ai"
$envFile = Join-Path $src ".env"
if (-not (Test-Path $envFile)) { Copy-Item (Join-Path $src ".env.example") $envFile; Ok "created src\.env from src\.env.example" } else { Ok "src\.env exists" }

function Get-EnvValue($name) {
    $line = Get-Content $envFile | Where-Object { $_ -match "^\s*$name\s*=" } | Select-Object -First 1
    if ($line) { return ($line -split "=", 2)[1].Trim().Trim('"') } else { return "" }
}
function Set-EnvValue($name, $value) {
    $lines = @(Get-Content $envFile)
    $found = $false
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match "^\s*#?\s*$name\s*=") { $lines[$i] = "$name=$value"; $found = $true; break }
    }
    if (-not $found) { $lines += "$name=$value" }
    [IO.File]::WriteAllLines($envFile, $lines, (New-Object Text.UTF8Encoding $false))
}
function Read-Watsonx {
    Info "Create an API key at https://cloud.ibm.com/iam/apikeys and copy the project ID from your watsonx.ai project (Manage tab)."
    $sec = Read-Host "  IBM Cloud API key (input hidden)" -AsSecureString
    $key = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
    $project = Read-Host "  watsonx.ai project ID"
    Write-Host "  Region: 1) Frankfurt eu-de  2) Dallas us-south  3) London eu-gb  4) Tokyo jp-tok  5) Sydney au-syd"
    $r = Read-Host "  Choose 1-5 [1]"
    $region = @{ "1" = "eu-de"; "2" = "us-south"; "3" = "eu-gb"; "4" = "jp-tok"; "5" = "au-syd" }[$(if ($r) { $r.Trim() } else { "1" })]
    if (-not $region) { $region = "eu-de" }
    if ($key) { Set-EnvValue "WATSONX_API_KEY" $key.Trim() }
    if ($project) { Set-EnvValue "WATSONX_PROJECT_ID" $project.Trim() }
    Set-EnvValue "WATSONX_URL" "https://$region.ml.cloud.ibm.com"
    Ok "saved to src\.env (this file is git-ignored; never commit it)"
}

$placeholders = @("", "your_ibm_cloud_api_key", "your_watsonx_project_id")
$configured = -not ($placeholders -contains (Get-EnvValue "WATSONX_API_KEY") -or $placeholders -contains (Get-EnvValue "WATSONX_PROJECT_ID"))
if (-not $configured) {
    Miss "watsonx.ai credentials are not set (optional)"
    Info "Without them CrimeFIR still runs fully locally: uncertain FIRs go to the officer review queue and"
    Info "station briefs use a template instead of IBM Granite."
    if (Ask "Enter IBM watsonx.ai credentials now?" $true) { if (-not $Yes) { Read-Watsonx; $configured = $true } else { Info "skipped in -Yes mode (needs typing)" } }
}
if ($configured -and (Test-Path $msPy) -and $summary["model_service"] -eq "OK") {
    & $msPy $doctor watsonx | Out-Host
    if ($LASTEXITCODE -ne 0 -and -not $Yes -and (Ask "The check failed. Re-enter the credentials?" $true)) {
        Read-Watsonx; & $msPy $doctor watsonx | Out-Host
    }
    if ($LASTEXITCODE -eq 0) {
        $summary["watsonx.ai"] = "OK"
        if (Ask "Send one tiny test request (~20 tokens) to confirm the project ID?" $true) {
            & $msPy $doctor watsonx --ping | Out-Host
            if ($LASTEXITCODE -ne 0) { $summary["watsonx.ai"] = "key OK, project check FAILED" }
        }
    } else { $summary["watsonx.ai"] = "FAILED (runs without the LLM)" }
} elseif (-not $configured) { $summary["watsonx.ai"] = "not configured (optional)" }

# ------------------------------------------------------------------------------------------------ 6 tests
Step 6 "Automated tests (optional)"
$caPy = Join-Path $src "core_api\.venv\Scripts\python.exe"
if ((Test-Path $caPy) -and $summary["core_api"] -eq "OK" -and (Ask "Run the core API tests (no GPU or internet needed, ~1-2 minutes)?" $false)) {
    Push-Location (Join-Path $src "core_api"); & $caPy -m pytest -q -p no:warnings; $t = $LASTEXITCODE; Pop-Location
    $summary["tests"] = $(if ($t -eq 0) { "passed" } else { "FAILED" })
} else { $summary["tests"] = "not run" }

# ------------------------------------------------------------------------------------------------ 7 summary + start
Step 7 "Summary"
foreach ($k in $summary.Keys) {
    $v = $summary[$k]
    $colour = if ($v -eq "OK" -or $v -eq "passed") { "Green" } elseif ($v -match "FAIL") { "Red" } else { "Yellow" }
    Write-Host ("  {0,-16} {1}" -f $k, $v) -ForegroundColor $colour
}
$blocking = @("core_api", "model_service", "frontend") | Where-Object { $summary[$_] -ne "OK" }
if ($blocking) {
    Write-Host "`n  Not ready to start: $($blocking -join ', '). Fix the items above and run setup.ps1 again." -ForegroundColor Yellow
    exit 1
}
Write-Host "`n  Setup complete. To start CrimeFIR later:  powershell -ExecutionPolicy Bypass -File scripts\start_all.ps1" -ForegroundColor Green
if (-not $NoStart -and (Ask "Start CrimeFIR now?" $true)) {
    & (Join-Path $PSScriptRoot "start_all.ps1") -Yes:$Yes
}
