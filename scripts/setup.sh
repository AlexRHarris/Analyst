#!/usr/bin/env bash
set -euo pipefail
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
echo
echo "Setup OK. Next steps:"
echo "  1. Install Ollama (https://ollama.com), then: ollama pull qwen2.5:7b"
echo "  2. Install Tesseract:"
echo "       Linux: sudo apt install tesseract-ocr"
echo "       Mac:   brew install tesseract"
echo "       Win:   https://github.com/UB-Mannheim/tesseract/wiki"
echo "  3. analyst build-index --sets <recent_set_codes>   # e.g. --sets blb,dsk,fdn"
echo "  4. Edit config/default.yaml: set capture.server_url and perception.regions"
echo "  5. On the Linux box:    analyst serve"
echo "  6. On the Windows box:  analyst capture"
