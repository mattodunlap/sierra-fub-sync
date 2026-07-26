@echo off
cd /d "%~dp0"
python -m pip install --quiet requests
python probe_joan.py jnikolaus36@gmail.com > joan_probe.txt 2>&1
type joan_probe.txt
echo.
pause
