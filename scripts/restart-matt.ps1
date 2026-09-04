# Restart Matt (RFP Rockstar) - wired to the desktop "Restart Matt" icon.
# Kills the server on port 8010, relaunches via the scheduled task, waits
# for health, then tells you how it went. -Silent skips the popup (for
# scripted use).

param([switch]$Silent)

$ErrorActionPreference = 'SilentlyContinue'

# stop whatever is serving port 8010 (the app) and 8030 (Matt's voice
# sidecar); the scheduled task relaunches both. Voice takes ~40s to
# reload and the app speaks via Magpie in the meantime.
foreach ($p in 8010, 8030) {
  Get-NetTCPConnection -State Listen -LocalPort $p -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique |
    ForEach-Object { Stop-Process -Id $_ -Force -Confirm:$false }
}
Start-Sleep -Seconds 2

# relaunch through the autostart task
Start-ScheduledTask -TaskName 'RFP Rockstar'

# wait for the API to come back (up to ~40s)
$ok = $false
foreach ($i in 1..20) {
  Start-Sleep -Seconds 2
  try {
    $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8010/api/health' -TimeoutSec 4 -UseBasicParsing
    if ($r.StatusCode -eq 200) { $ok = $true; break }
  } catch {}
}

if ($Silent) { if ($ok) { exit 0 } else { exit 1 } }

Add-Type -AssemblyName PresentationFramework | Out-Null
if ($ok) {
  [System.Windows.MessageBox]::Show(
    "Matt is back up and rockin'.`n`nhttps://desktop-pgbumck.taild4dc6f.ts.net",
    'RFP Rockstar', 'OK', 'Information') | Out-Null
} else {
  [System.Windows.MessageBox]::Show(
    "Matt didn't come back within 40 seconds. Check logs\ in the " +
    "MissionRFP folder, or run this again.",
    'RFP Rockstar', 'OK', 'Warning') | Out-Null
}
