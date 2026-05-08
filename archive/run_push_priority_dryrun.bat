@echo off
REM DRY RUN - shows which Sierra 'SPRIORITY' leads need the tag added in FUB.
cd /d "%~dp0"
python -m pip install --quiet requests
python push_priority_tag.py "SPRIORITY"
echo.
pause
