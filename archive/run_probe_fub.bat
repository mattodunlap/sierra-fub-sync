@echo off
cd /d "%~dp0"
python -m pip install --quiet requests
python probe_fub_endpoints.py
echo.
pause
