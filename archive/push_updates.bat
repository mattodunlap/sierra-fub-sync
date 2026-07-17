@echo off
REM Push the latest local changes (script fixes, debug tools, deploy guide) to GitHub.
REM Safe to run anytime. Skips if there's nothing to commit.

cd /d "%~dp0"

echo ===========================================
echo  Push updates to GitHub
echo ===========================================
echo.

echo Staging changes...
git add .

echo.
echo Committing...
git commit -m "Add 429 retry logic, error logging, debug tools, deploy guide"

echo.
echo Pushing...
git push

echo.
if errorlevel 1 (
    echo Push failed - read errors above. Common cause: nothing changed.
) else (
    echo SUCCESS - changes are on GitHub.
)
echo.
pause
