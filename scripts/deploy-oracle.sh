#!/usr/bin/env bash
# RFP Rockstar - one-shot setup on a fresh Ubuntu VM (Oracle Always Free).
#
# Run as the default 'ubuntu' user:
#   curl -fsSL https://raw.githubusercontent.com/robsalsman/MT-RFP/main/scripts/deploy-oracle.sh | bash
#
# What it does:
#   1. Installs Python + git, clones the repo, installs backend deps
#   2. Unpacks ~/rfp-rockstar-bundle.zip (data/, .env, frontend/dist) if
#      you've uploaded one - otherwise the app starts fresh
#   3. Installs a systemd service (auto-start on boot, restart on crash)
#   4. Installs Tailscale and publishes the app on a PERMANENT public
#      HTTPS URL via Funnel - no firewall/port configuration needed
#      (Funnel is outbound-only, so Oracle's default block-all inbound
#      rules can stay exactly as they are)
set -euo pipefail

APP_DIR="$HOME/MT-RFP"
BUNDLE="$HOME/rfp-rockstar-bundle.zip"
PORT=8000

echo "== 1/5 packages =="
sudo apt-get update -q
sudo apt-get install -y -q python3-venv python3-pip git unzip

echo "== 2/5 app =="
if [ ! -d "$APP_DIR" ]; then
  git clone https://github.com/robsalsman/MT-RFP.git "$APP_DIR"
else
  git -C "$APP_DIR" pull --ff-only
fi
cd "$APP_DIR"
python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r backend/requirements.txt

if [ -f "$BUNDLE" ]; then
  echo "== unpacking data bundle =="
  unzip -o -q "$BUNDLE" -d "$APP_DIR"
else
  echo "== no bundle found at $BUNDLE - starting fresh =="
fi

echo "== 3/5 systemd service =="
sudo tee /etc/systemd/system/rfp-rockstar.service >/dev/null <<EOF
[Unit]
Description=RFP Rockstar (Mission Telecom RFP intelligence)
After=network-online.target
Wants=network-online.target

[Service]
User=$USER
WorkingDirectory=$APP_DIR/backend
ExecStart=$APP_DIR/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port $PORT
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now rfp-rockstar
sleep 5
curl -fsS "http://127.0.0.1:$PORT/api/health" >/dev/null \
  && echo "   app is up" || { echo "   APP FAILED - journalctl -u rfp-rockstar"; exit 1; }

echo "== 4/5 tailscale =="
if ! command -v tailscale >/dev/null; then
  curl -fsSL https://tailscale.com/install.sh | sh
fi
if ! sudo tailscale status >/dev/null 2>&1; then
  echo ""
  echo ">>> A login link will print below - open it in YOUR browser and"
  echo ">>> approve this machine into your tailnet, then setup continues."
  sudo tailscale up
fi

echo "== 5/5 funnel (permanent public URL) =="
sudo tailscale funnel --bg $PORT
sudo tailscale funnel status
echo ""
echo "DONE. Share the https://...ts.net URL above with the team."
echo "It survives reboots: the service auto-starts and Funnel persists."
