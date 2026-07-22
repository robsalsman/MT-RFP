# RFP Rockstar - start the API/app server (and optionally a Cloudflare quick
# tunnel) on logon. Registered as a Scheduled Task by install-autostart.ps1.
#
#   -Port      port to serve on (default 8010)
#   -Tunnel    also start a Cloudflare quick tunnel (URL changes each run).
#              Omit this once Tailscale Funnel is live - Funnel is permanent.

param(
  [int]$Port = 8010,
  [switch]$Tunnel
)

$ErrorActionPreference = 'Stop'
$root    = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root 'backend'
$logDir  = Join-Path $root 'logs'
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }

$stamp     = Get-Date -Format 'yyyy-MM-dd'
$serverLog = Join-Path $logDir "server-$stamp.log"
$tunnelLog = Join-Path $logDir "tunnel-$stamp.log"

# Don't start a second copy if the port is already served.
$busy = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
if ($busy) {
  Add-Content $serverLog "[$(Get-Date -f o)] port $Port already listening - not starting a duplicate"
  exit 0
}

Add-Content $serverLog "[$(Get-Date -f o)] starting uvicorn on 127.0.0.1:$Port"
Start-Process -FilePath 'python' `
  -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port',"$Port") `
  -WorkingDirectory $backend `
  -RedirectStandardOutput $serverLog -RedirectStandardError "$serverLog.err" `
  -WindowStyle Hidden

if ($Tunnel) {
  $cf = Join-Path $env:USERPROFILE 'cloudflared.exe'
  if (Test-Path $cf) {
    Add-Content $tunnelLog "[$(Get-Date -f o)] starting cloudflare quick tunnel -> $Port"
    Start-Process -FilePath $cf `
      -ArgumentList @('tunnel','--url',"http://localhost:$Port") `
      -RedirectStandardOutput $tunnelLog -RedirectStandardError "$tunnelLog.err" `
      -WindowStyle Hidden
  } else {
    Add-Content $tunnelLog "[$(Get-Date -f o)] cloudflared.exe not found at $cf - skipped"
  }
}
