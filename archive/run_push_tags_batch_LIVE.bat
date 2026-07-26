@echo off
REM LIVE - reads tags_to_push.txt and pushes each tag from Sierra to FUB.
cd /d "%~dp0"
echo This will push every tag listed in tags_to_push.txt
echo from Sierra to FUB. Existing FUB tags are preserved.
echo.
type tags_to_push.txt
echo.
pause
python -m pip install --quiet requests
python push_tags_batch.py --write
echo.
pause
