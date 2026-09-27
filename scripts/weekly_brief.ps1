# Generates a weekly station crime brief headlessly with IBM Bob Shell (bob run), using the CrimeFIR MCP tools.
# Usage:  ./scripts/weekly_brief.ps1 -Station "Navrangpura" [-MaxCost 2]
# Requires: Bob Shell v2 logged in, CrimeFIR core API running, .bob/mcp.json in this repo.
# Status: written against the Bob Shell docs, NOT yet run (no Bob install on the dev machine). The MCP tools it uses are
# verified with src/mcp_server/smoke_test.py.
param(
    [Parameter(Mandatory = $true)][string]$Station,
    [double]$MaxCost = 2
)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$outDir = Join-Path $repo "var\briefs"
New-Item -ItemType Directory -Force $outDir | Out-Null
$stamp = Get-Date -Format "yyyy-MM-dd"
$prompt = "Using the CrimeFIR tools, write the weekly crime intelligence brief for $Station police station for " +
          "the last 7 days of data: call station_trends and list_flagged_offenders for this station, then summarise " +
          "rising crime types, active repeat-offender clusters with their key identifiers and suggested actions. " +
          "Cite FIR and cluster ids. Links are leads needing verification."
$result = bob run --mode fir-analyst --format json --max-cost $MaxCost --workspace $repo $prompt
$outFile = Join-Path $outDir "brief-$($Station -replace '\W','_')-$stamp.json"
$result | Out-File -Encoding utf8 $outFile
Write-Host "Brief saved to $outFile"
