#!/bin/bash
# =============================================================================
# Milan AI Week Hackathon - Google Cloud VM Setup Script
#
# Run this INSIDE the VM (Ubuntu 22.04) after SSH:
#   gcloud compute ssh trading-agent-vm --zone=europe-west1-b
#
# This script:
#   - Installs Miniconda (Python 3.13 env)
#   - Installs Kraken CLI
#   - Clones your repo (optional) and installs deps
#   - Creates a systemd service to run 24/7
# =============================================================================
set -euo pipefail

# -------------------------
# User-configurable settings
# -------------------------
# If your repo is public, set REPO_URL and the script will clone it.
# Example:
#   export REPO_URL="https://github.com/YOUR_USERNAME/YOUR_HACKATHON_REPO.git"
#   export REPO_BRANCH="main"
#   export INSTALL_DIR="$HOME/project"
REPO_URL="${REPO_URL:-}"
REPO_BRANCH="${REPO_BRANCH:-main}"
INSTALL_DIR="${INSTALL_DIR:-$HOME/project}"
SERVICE_NAME="${SERVICE_NAME:-trading-agent}"

echo "=== [1/7] System packages ==="
sudo apt-get update -y
sudo apt-get upgrade -y
sudo apt-get install -y git curl ca-certificates build-essential unzip

echo "=== [2/7] Install Miniconda ==="
if [ ! -d "$HOME/miniconda3" ]; then
  curl -fsSLo /tmp/miniconda.sh https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
  bash /tmp/miniconda.sh -b -p "$HOME/miniconda3"
fi
export PATH="$HOME/miniconda3/bin:$PATH"
echo "Conda version: $(conda --version)"

echo "=== [3/7] Create Python 3.13 env ==="
if ! conda env list | awk '{print $1}' | grep -qx "tradingagents"; then
  conda create -n tradingagents python=3.13 -y
fi

echo "=== [4/7] Install Kraken CLI ==="
if ! command -v kraken >/dev/null 2>&1; then
  curl --proto '=https' --tlsv1.2 -LsSf \
    https://github.com/krakenfx/kraken-cli/releases/latest/download/kraken-cli-installer.sh | sh
  export PATH="$HOME/.cargo/bin:$PATH"
fi
kraken --version

echo "=== [5/7] Get project code ==="
if [ -n "$REPO_URL" ]; then
  if [ -d "$INSTALL_DIR/.git" ]; then
    echo "Repo already exists at $INSTALL_DIR; pulling latest..."
    git -C "$INSTALL_DIR" fetch --all
    git -C "$INSTALL_DIR" checkout "$REPO_BRANCH"
    git -C "$INSTALL_DIR" pull --ff-only
  else
    git clone --branch "$REPO_BRANCH" "$REPO_URL" "$INSTALL_DIR"
  fi
else
  echo "REPO_URL not set; assuming project already present at $INSTALL_DIR"
fi

echo "=== [6/7] Install Python dependencies ==="
cd "$INSTALL_DIR"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate tradingagents
python -m pip install -U pip
python -m pip install -r requirements.txt
python -m pip install -e TradingAgents

if [ ! -f ".env" ] && [ -f ".env.example" ]; then
  cp .env.example .env
  echo "Created .env from .env.example at $INSTALL_DIR/.env (fill in keys)."
fi

echo "=== [7/7] Install systemd service ==="
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}.service"
sudo tee "$SERVICE_PATH" >/dev/null <<EOF
[Unit]
Description=Autonomous Trading Agent (Kraken CLI + TradingAgents)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
Environment=PATH=$HOME/miniconda3/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$HOME/.cargo/bin
EnvironmentFile=$INSTALL_DIR/.env
ExecStart=$HOME/miniconda3/bin/conda run -n tradingagents python -u bridge/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}.service"

echo ""
echo "=== Setup complete ==="
echo ""
echo "1) Edit API keys on the VM:"
echo "   nano $INSTALL_DIR/.env"
echo ""
echo "2) Start the agent (paper mode by default):"
echo "   sudo systemctl start ${SERVICE_NAME}.service"
echo ""
echo "3) Tail logs:"
echo "   journalctl -u ${SERVICE_NAME}.service -f"
echo ""
echo "4) Verify Kraken paper mode:"
echo "   kraken paper status -o json"

