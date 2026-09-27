# Uploads a FIR file to the running core API and waits until processing finishes (Windows).
# Usage:  scripts\load_dataset.ps1                      # the 400-FIR dataset
#         scripts\load_dataset.ps1 -File src\dataset\demo_live_batch.txt
#         scripts\load_dataset.ps1 -Reset               # wipe all data first
param(
    [string]$File = "src\dataset\firs_main.txt",
    [string]$Api = "http://127.0.0.1:8000",
    [switch]$Reset
)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$path = Join-Path $repo $File
if ($Reset) { Invoke-RestMethod -Method Post "$Api/api/system/reset" | Out-Null; Write-Host "All data wiped." }

$raw = curl.exe -s -F "file=@$path" "$Api/api/batches"
$accepted = $raw | ConvertFrom-Json
if (-not $accepted.batch_id) { throw "Upload failed: $raw" }
Write-Host "Batch $($accepted.batch_id): $($accepted.created) new FIRs, $($accepted.duplicates) duplicates"
do {
    Start-Sleep -Seconds 3
    $b = Invoke-RestMethod "$Api/api/batches/$($accepted.batch_id)"
    Write-Host ("  {0}  {1}/{2} FIRs done" -f $b.status, $b.firs_done, $b.created)
} while ($b.status -in @("RECEIVED", "PROCESSING", "LINKING"))
Write-Host "Finished: $($b.status). Open http://localhost:3000" -ForegroundColor Green
