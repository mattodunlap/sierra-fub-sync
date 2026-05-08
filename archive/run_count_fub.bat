@echo off
cd /d "%~dp0"
python -m pip install --quiet requests
python count_fub_populated.py
echo.
pause
