@echo off
cd /d "%~dp0"
python -m pip install --quiet requests
python probe_sierra_tags.py > sierra_tags_probe.txt 2>&1
type sierra_tags_probe.txt
echo.
echo Output also saved to sierra_tags_probe.txt
echo.
pause
