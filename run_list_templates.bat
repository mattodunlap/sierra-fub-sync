@echo off
cd /d "%~dp0"
python -m pip install --quiet requests
python list_fub_templates.py
echo.
pause
