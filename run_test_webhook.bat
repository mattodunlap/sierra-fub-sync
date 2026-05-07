@echo off
cd /d "%~dp0"
python -m pip install --quiet requests
python test_webhook.py
echo.
pause
