@echo off
REM Test the sync on a single lead. By default this is a DRY RUN - no writes.
REM Edit the EMAIL line below to a real lead email from your Sierra/FUB.
REM To actually write to FUB, change DRYRUN=--write below.

cd /d "%~dp0"

set EMAIL=love_abundantly@me.com
set DRYRUN=--write

echo Running test on: %EMAIL% (dry run = %DRYRUN% empty means yes, dry run)
echo.
python test_one_lead.py %EMAIL% %DRYRUN%
echo.
pause
