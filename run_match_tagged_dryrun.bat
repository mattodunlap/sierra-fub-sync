@echo off
REM DRY RUN - identifies what would happen for tagged contacts.
REM Unmatched contacts get the generic fallback URL (https://www.thevegasagent.com/?sentfrom=auto).
REM Edit the TAG line below to change the tag.

cd /d "%~dp0"

set TAG=Needs Sierra URL

echo Searching for FUB contacts tagged: %TAG%
echo (DRY RUN - no changes will be made)
echo Unmatched contacts will receive a generic fallback URL.
echo.
python -m pip install --quiet requests
python match_tagged_contacts.py "%TAG%" --fallback-generic
echo.
pause
