@echo off
REM Full backfill: writes the Sierra auto-login URL into FUB for every matching lead.
REM Estimated runtime: 2-4 hours for ~10K leads.
REM Safe to re-run if interrupted - it skips contacts that are already correct.

cd /d "%~dp0"

echo =========================================================
echo  FULL BACKFILL - Sierra to FUB Auto-Login URL Sync
echo =========================================================
echo.
echo This will:
echo   - Pull every lead from Sierra (~10,388 leads)
echo   - Match them to FUB contacts by email
echo   - Write each one's auto-login URL into FUB's custom field
echo.
echo Estimated runtime: 2-4 hours
echo.
echo Important:
echo   - Don't close this window once it starts
echo   - Don't let your computer sleep (recommend plugging in
echo     and disabling sleep in Power Settings)
echo   - Safe to interrupt with Ctrl+C and re-run later -
echo     it skips contacts that are already correct
echo.
pause

echo.
echo Installing dependencies...
python -m pip install --quiet requests

echo.
echo Starting at %date% %time%
echo =========================================================
python sierra_fub_sync.py
echo =========================================================
echo Finished at %date% %time%
echo.
pause
