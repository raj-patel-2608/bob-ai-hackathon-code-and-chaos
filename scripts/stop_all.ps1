# Stops the CrimeFIR services (Windows): whatever is listening on ports 8100, 8000 and 3000. Asks first.
#   powershell -ExecutionPolicy Bypass -File scripts\stop_all.ps1        (-Yes to skip the question)
# Your data stays in var\crimefir.db; start again with scripts\start_all.ps1.
param([switch]$Yes)

$services = @(@{ Port = 8100; Name = "model service" }, @{ Port = 8000; Name = "core API" }, @{ Port = 3000; Name = "frontend" })
$found = @()
foreach ($s in $services) {
    $conn = Get-NetTCPConnection -LocalPort $s.Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($conn) {
        $proc = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
        $found += [pscustomobject]@{ Port = $s.Port; Service = $s.Name; Pid = $conn.OwningProcess; Process = $proc.ProcessName }
    }
}
if (-not $found) { Write-Host "Nothing is running on ports 8100, 8000 or 3000."; exit 0 }
$found | Format-Table -AutoSize | Out-Host
if (-not $Yes) {
    $a = Read-Host "Stop these processes? [Y/n]"
    if (-not ([string]::IsNullOrWhiteSpace($a) -or $a.Trim() -match '^(y|yes)$')) { Write-Host "Nothing stopped."; exit 0 }
}
foreach ($f in $found) {
    Stop-Process -Id $f.Pid -Force -ErrorAction SilentlyContinue
    Write-Host ("  stopped {0} (port {1}, pid {2})" -f $f.Service, $f.Port, $f.Pid) -ForegroundColor Green
}
Write-Host "The service windows can be closed. Data is kept in var\crimefir.db."
