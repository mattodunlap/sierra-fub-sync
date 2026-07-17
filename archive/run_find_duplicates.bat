@echo off
REM Read-only scan for duplicate FUB contacts (same email or phone).
REM Output saved to fub_duplicates.txt for review.

cd /d "%~dp0"
python -m pip install --quiet requests
python find_fub_duplicates.py
echo.
pause
