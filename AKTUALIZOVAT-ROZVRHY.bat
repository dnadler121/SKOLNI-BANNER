@echo off
cd /d "%~dp0"
title Aktualizace rozvrhu - skolni banner

if not exist ".venv\Scripts\python.exe" (
    echo Prvni spusteni - pripravuji prostredi...
    py -m venv .venv
    if errorlevel 1 goto chyba
    call .venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    pip install -r requirements-sync.txt
    python -m playwright install chromium
) else (
    call .venv\Scripts\activate.bat
)

echo.
python synchronizace_rozvrhu.py
echo.
pause
exit /b 0

:chyba
echo.
echo Nepodarilo se najit Python. Nainstalujte Python 3 a pri instalaci zaskrtnete "Add Python to PATH".
pause
exit /b 1
