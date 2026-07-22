# RFP Rockstar - expose the app on a PERMANENT public URL via Tailscale Funnel.
# Run this AFTER you have logged in with:  tailscale up
#
# Funnel config is stored by tailscaled and survives reboots, so unlike the
# Cloudflare quick tunnel the URL never changes.

param([int]$Port = 8010)

$ErrorActionPreference = 'Stop'
$ts = 'C:\Program Files\Tailscale\tailscale.exe'
if (-not (Test-Path $ts)) { throw "tailscale.exe not found at $ts" }

# 1. must be logged in
$status = & $ts status 2>&1 | Out-String
if ($status -match 'Logged out') {
  Write-Output 'Not logged in yet. Run:   & "C:\Program Files\Tailscale\tailscale.exe" up'
  Write-Output 'Then re-run this script.'
  exit 1
}

# 2. app must actually be serving
try { $null = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 5 -UseBasicParsing }
catch { Write-Output "App is not responding on port $Port. Start it first (scripts\start-rfp-rockstar.ps1)."; exit 1 }

# 3. publish it (background = persists across restarts)
Write-Output "Publishing http://127.0.0.1:$Port via Funnel..."
& $ts funnel --bg $Port
Write-Output ''
Write-Output '--- Funnel status ---'
& $ts funnel status
Write-Output ''
Write-Output 'Share the https://<machine>.<tailnet>.ts.net URL above. It is permanent.'
Write-Output 'To take it offline later:  tailscale funnel --https=443 off'
