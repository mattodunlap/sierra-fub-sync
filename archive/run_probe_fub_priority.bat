@echo off
cd /d "%~dp0"
python -m pip install --quiet requests
python probe_fub_priority.py > fub_priority_probe.txt 2>&1
type fub_priority_probe.txt
echo.
pause
