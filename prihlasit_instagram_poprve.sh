#!/usr/bin/env bash
set -e
PROFILE="$HOME/.school-banner-kiosk-profile"
BROWSER=""
for b in chromium chromium-browser google-chrome google-chrome-stable; do
  if command -v "$b" >/dev/null 2>&1; then BROWSER="$b"; break; fi
done
if [ -z "$BROWSER" ]; then
  echo "Nenalezen Chromium/Chrome."
  exit 1
fi
# Jednorázové servisní spuštění. Přihlaste Instagram a okno zavřete.
exec "$BROWSER" --user-data-dir="$PROFILE" "https://www.instagram.com/sssaskv/"
