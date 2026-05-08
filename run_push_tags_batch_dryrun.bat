@echo off
REM DRY RUN - reads tags_to_push.txt and shows what would happen for each tag.
cd /d "%~dp0"
python -m pip install --quiet requests
python push_tags_batch.py
echo.
pause
