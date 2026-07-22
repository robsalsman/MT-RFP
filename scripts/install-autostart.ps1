# Register RFP Rockstar to start automatically at logon (per-user Scheduled
# Task - no admin rights, no system/security settings touched).
#
#   .\install-autostart.ps1              # server only (use with Tailscale Funnel)
#   .\install-autostart.ps1 -Tunnel      # server + Cloudflare quick tunnel
#   .\install-autostart.ps1 -Remove      # unregister

param(
  [int]$Port = 8010,
  [switch]$Tunnel,
  [switch]$Remove
)

$ErrorActionPreference = 'Stop'
$taskName = 'RFP Rockstar'
$starter  = Join-Path $PSScriptRoot 'start-rfp-rockstar.ps1'

if ($Remove) {
  try { Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction Stop
        Write-Output "Removed scheduled task '$taskName'." }
  catch { Write-Output "No scheduled task '$taskName' to remove." }
  return
}

$argList = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$starter`" -Port $Port"
if ($Tunnel) { $argList += ' -Tunnel' }

$action   = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $argList
$trigger  = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
# Keep it alive on laptops: don't stop on battery, retry if it fails early.
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries -StartWhenAvailable `
  -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
  -ExecutionTimeLimit ([TimeSpan]::Zero)

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
  -Settings $settings -Description 'Starts the RFP Rockstar app server at logon.' `
  -Force | Out-Null

Write-Output "Registered '$taskName' to run at logon (port $Port, tunnel=$Tunnel)."
Write-Output "Start it now with:  Start-ScheduledTask -TaskName '$taskName'"
