@echo off
REM LIVE - adds '2026 Daily Search Done' tag to matching FUB contacts.
cd /d "%~dp0"
echo This will push the '2026 Daily Search Done' tag from Sierra to FUB
echo for any contact where Sierra has it but FUB doesn't.
echo Existing FUB tags are preserved.
echo.
pause
python -m pip install --quiet requests
python push_priority_tag.py "2026 Daily Search Done" --write
echo.
pause
