@echo off
REM LIVE WRITE - pushes URL updates to FUB.
REM Matched contacts get their personalized auto-login URL.
REM Unmatched contacts get the generic fallback URL.
REM Edit the TAG line below to change the tag.

cd /d "%~dp0"

set TAG=Needs Sierra URL

echo Searching for FUB contacts tagged: %TAG%
echo LIVE WRITE - real updates will happen.
echo Unmatched will get https://www.thevegasagent.com/?sentfrom=auto
echo.
pause

python -m pip install --quiet requests
python match_tagged_contacts.py "%TAG%" --write --fallback-generic
echo.
pause
