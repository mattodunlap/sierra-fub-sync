@echo off
REM DRY RUN - shows which Sierra '2026 Daily Search Done' leads need the tag added in FUB.
cd /d "%~dp0"
python -m pip install --quiet requests
python push_priority_tag.py "2026 Daily Search Done"
echo.
pause
