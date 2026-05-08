@echo off
cd /d "%~dp0"
python -m pip install --quiet requests
python peek_template.py 256
echo.
pause
