#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

echo "=============================================="
echo "  AKTUALIZACE ROZVRHU - SKOLNI BANNER"
echo "=============================================="
echo

if [ ! -d ".venv" ]; then
    echo "Prvni spusteni - vytvarim virtualni prostredi..."
    python3 -m venv .venv
fi

source .venv/bin/activate

echo "Kontroluji Python balicky..."
python -m pip install --upgrade pip
pip install -r requirements-sync.txt

echo
echo "Kontroluji Chromium pro Playwright..."
python -m playwright install chromium

echo
echo "Spoustim synchronizaci..."
echo
python synchronizace_rozvrhu.py

echo
echo "=============================================="
echo "  HOTOVO - stiskni Enter pro ukonceni"
echo "=============================================="
read -r
