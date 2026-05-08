@echo off
cd /d "%~dp0"
python -m pip install --quiet requests
python probe_sierra.py
echo.
pause
