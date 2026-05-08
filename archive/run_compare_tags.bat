@echo off
REM Read-only sample comparison of tags between FUB and Sierra.
cd /d "%~dp0"
python -m pip install --quiet requests
python compare_tags.py
echo.
pause
