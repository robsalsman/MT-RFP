# Bundle everything the cloud server needs from this laptop:
#   data/           (SQLite DB: RFPs, leads board, drafts, users, statuses)
#   .env            (NVIDIA API key etc.)
#   frontend/dist   (built UI - the VM doesn't need Node)
# Output: rfp-rockstar-bundle.zip on your Desktop, ready to scp to the VM.

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$out  = Join-Path ([Environment]::GetFolderPath('Desktop')) 'rfp-rockstar-bundle.zip'

Push-Location $root
try {
  if (-not (Test-Path 'frontend/dist/index.html')) {
    Write-Output 'frontend/dist missing - run "npm run build" in frontend/ first.'
    exit 1
  }
  if (Test-Path $out) { Remove-Item $out -Force }
  # stage so paths inside the zip mirror the repo layout exactly
  # (Compress-Archive would otherwise flatten frontend/dist to dist/)
  $stage = Join-Path $env:TEMP 'rfp-bundle-stage'
  if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
  New-Item -ItemType Directory -Path (Join-Path $stage 'frontend') | Out-Null
  Copy-Item 'data' (Join-Path $stage 'data') -Recurse
  Copy-Item '.env' (Join-Path $stage '.env')
  Copy-Item 'frontend/dist' (Join-Path $stage 'frontend/dist') -Recurse
  Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $out
  Remove-Item $stage -Recurse -Force
  $mb = [math]::Round((Get-Item $out).Length / 1MB, 1)
  Write-Output "Bundle ready: $out ($mb MB)"
  Write-Output ''
  Write-Output 'Upload it to the VM with (use the key file Oracle gave you):'
  Write-Output '  scp -i <your-key.pem> "$HOME\Desktop\rfp-rockstar-bundle.zip" ubuntu@<VM-PUBLIC-IP>:~/'
} finally { Pop-Location }
