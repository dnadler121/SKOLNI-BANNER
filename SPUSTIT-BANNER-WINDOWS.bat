@echo off
cd /d "%~dp0"
if not exist .venv (
  py -m venv .venv
  call .venv\Scripts\activate.bat
  python -m pip install --upgrade pip
  pip install -r requirements.txt
)
call .venv\Scripts\activate.bat
python kiosk_windows.py
