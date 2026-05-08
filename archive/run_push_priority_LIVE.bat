@echo off
REM LIVE - adds 'SPRIORITY' tag to matching FUB contacts.
cd /d "%~dp0"
echo This will push the 'SPRIORITY' tag from Sierra to FUB
echo for any contact where Sierra has it but FUB doesn't.
echo Existing FUB tags are preserved.
echo.
pause
python -m pip install --quiet requests
python push_priority_tag.py "SPRIORITY" --write
echo.
pause
