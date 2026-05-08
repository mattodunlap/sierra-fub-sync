@echo off
cd /d "%~dp0"
python -m pip install --quiet requests
python debug_page2.py
echo.
pause
