@echo off
cd /d "%~dp0"
python -m pip install --quiet requests
python investigate_priority_gap.py > priority_gap_investigation.txt 2>&1
type priority_gap_investigation.txt
echo.
pause
