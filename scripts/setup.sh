#!/usr/bin/env bash
set -euo pipefail

# Pick whichever python is available.
if command -v python3 >/dev/null 2>&1; then
    PY=python3
elif command -v python >/dev/null 2>&1; then
    PY=python
else
    echo "ERROR: no python3 found. Install Python 3.11+ first:"
    echo "  Ubuntu/Debian: sudo apt install python3 python3-venv python3-pip"
    echo "  Fedora:        sudo dnf install python3 python3-pip"
    echo "  Arch:          sudo pacman -S python python-pip"
    echo "  macOS:         brew install python@3.11"
    exit 1
fi

echo "Using $PY ($($PY --version))"
$PY -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -U pip
pip install -e .

echo
echo "Setup OK. Next steps:"
echo "  1. Install Ollama:  curl -fsSL https://ollama.com/install.sh | sh"
echo "       ollama pull qwen2.5vl:7b"
echo "  2. Edit config/default.yaml: set capture.server_url to the Linux box's LAN IP."
echo "  3. (Optional) Build phash index for stronger card-name accuracy:"
echo "       analyst build-index --sets <recent set codes>"
echo "  4. On the Linux box:    analyst serve"
echo "  5. On the Windows box:  analyst capture"
echo
echo "No region calibration needed — the VLM handles layout."
