#!/usr/bin/env bash
set -e

echo "[BANNER] Kontrola Chromium pro Playwright..."
python -m playwright install chromium

echo "[BANNER] Spoustim Flask/Gunicorn..."
exec gunicorn --timeout 120 app:app
