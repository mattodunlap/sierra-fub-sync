@echo off
REM DRY RUN - prints what would be replaced. Makes no changes to FUB.
cd /d "%~dp0"
python -m pip install --quiet requests
python replace_ylopo_to_sierra.py
echo.
pause
