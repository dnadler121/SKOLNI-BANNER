#!/usr/bin/env bash
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
PROFILE="$HOME/.school-banner-kiosk-profile"
EXT="$HERE/kiosk_extension"
URL="http://127.0.0.1:5000/"

BROWSER=""
for b in chromium chromium-browser google-chrome google-chrome-stable; do
  if command -v "$b" >/dev/null 2>&1; then BROWSER="$b"; break; fi
done
if [ -z "$BROWSER" ]; then
  echo "Nenalezen Chromium/Chrome. Nainstalujte Chromium a spusťte skript znovu."
  exit 1
fi

exec "$BROWSER" \
  --kiosk \
  --user-data-dir="$PROFILE" \
  --disable-pinch \
  --overscroll-history-navigation=0 \
  --disable-session-crashed-bubble \
  --no-first-run \
  --disable-features=Translate \
  --load-extension="$EXT" \
  "$URL"
