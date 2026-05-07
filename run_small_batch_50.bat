@echo off
REM Quick scale test - runs the live sync on the first 50 leads only.
REM Useful as a final sanity check before committing 2-4 hours to the full backfill.

cd /d "%~dp0"

echo Running live sync on first 50 leads (real writes to FUB)...
echo.
python -m pip install --quiet requests
python sierra_fub_sync.py --limit=50
echo.
pause
