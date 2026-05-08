@echo off
cd /d "%~dp0"
python -m pip install --quiet requests
python compare_priority_tag.py "S Priority"
echo.
pause
