@echo off
cd /d "%~dp0"
python -m pip install --quiet requests
python check_pagination.py
echo.
pause
