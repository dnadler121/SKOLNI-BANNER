#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then python3 -m venv .venv; fi
source .venv/bin/activate
pip -q install -r requirements.txt
python -m playwright install chromium
python kiosk_linux.py
