#!/bin/bash
# =============================================================================
# Milan AI Week Hackathon — Google Cloud VM Setup Script
# Run this INSIDE the VM after SSH-ing in:
#   gcloud compute ssh trading-agent-vm --zone=europe-west1-b
# =============================================================================
set -e

echo "=== [1/8] System update ==="
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y git curl screen build-essential

echo "=== [2/8] Install Node.js 20 (for Gemini CLI) ==="
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs
node --version && npm --version

echo "=== [3/8] Install Miniconda ==="
curl -O https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh -b -p "$HOME/miniconda3"
export PATH="$HOME/miniconda3/bin:$PATH"
conda init bash
source "$HOME/.bashrc" 2>/dev/null || true
echo "Conda version: $(conda --version)"

echo "=== [4/8] Install Kraken CLI (Rust binary) ==="
curl --proto '=https' --tlsv1.2 -LsSf \
  https://github.com/krakenfx/kraken-cli/releases/latest/download/kraken-cli-installer.sh | sh
export PATH="$HOME/.cargo/bin:$PATH"
kraken --version

echo "=== [5/8] Install Gemini CLI ==="
npm install -g @google/gemini-cli
gemini --version 2>/dev/null || echo "(gemini CLI installed; run 'gemini' to verify)"

echo "=== [6/8] Clone repos ==="
git clone https://github.com/TauricResearch/TradingAgents.git
# Clone your hackathon repo (replace with your actual GitHub URL):
# git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git project
# If uploading manually, skip the clone and just scp/rsync the project files.

echo "=== [7/8] Python environment ==="
conda create -n tradingagents python=3.11 -y
# shellcheck disable=SC1091
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate tradingagents

cd TradingAgents
pip install .
cd ..

# Install project dependencies (run from project root)
pip install python-dotenv schedule requests pandas google-generativeai

echo "=== [8/8] Configure API keys ==="
# Create .env from template — fill in your keys:
cat > .env << 'ENVEOF'
GOOGLE_API_KEY=FILL_IN
KRAKEN_API_KEY=FILL_IN
KRAKEN_API_SECRET=FILL_IN
ALPHA_VANTAGE_API_KEY=FILL_IN
ENVEOF

echo ""
echo ">>> FILL IN .env with your real API keys before starting the agent <<<"
echo ""

echo "=== Setup complete ==="
echo ""
echo "Start the agent:"
echo "  screen -dmS trading_agent bash -c 'source ~/miniconda3/etc/profile.d/conda.sh && conda activate tradingagents && python bridge/main.py'"
echo ""
echo "Attach to see logs:"
echo "  screen -r trading_agent"
echo ""
echo "Detach without stopping:"
echo "  Ctrl+A, then D"
echo ""
echo "Test paper balance:"
echo "  kraken paper status -o json"
echo ""
echo "Interactive Gemini+Kraken session:"
echo "  gemini  (then type: check my Kraken paper balance)"
