@echo off
REM LIVE WRITE - actually replaces tags in FUB. Saves backups to template_backups\.
REM Run the dryrun version first and verify the candidates list looks right.
cd /d "%~dp0"

echo ===========================================
echo  LIVE WRITE - will modify FUB templates
echo ===========================================
echo.
echo This will replace %%custom_ylopo_listing_alert%% with %%custom_sierra_login_url%%
echo in all matching email and SMS templates.
echo.
echo Backups will be saved to template_backups\ before each write.
echo.
pause

python -m pip install --quiet requests
python replace_ylopo_to_sierra.py --write
echo.
pause
