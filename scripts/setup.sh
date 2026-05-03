#!/usr/bin/env bash
set -euo pipefail
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
echo
echo "Setup OK. Next steps:"
echo "  1. Install Ollama: https://ollama.com"
echo "       ollama pull qwen2.5vl:7b"
echo "  2. Edit config/default.yaml: set capture.server_url to the Linux box's LAN IP."
echo "  3. (Optional) Build phash index for stronger card-name accuracy:"
echo "       analyst build-index --sets <recent set codes>"
echo "  4. On the Linux box:    analyst serve"
echo "  5. On the Windows box:  analyst capture"
echo
echo "That's it. No region calibration needed — the VLM handles layout."
