@echo off
REM Checks what's installed locally that we'll need for the deploy.

echo ===========================================
echo  Setup Check
echo ===========================================
echo.

echo [1/3] Checking for git...
git --version 2>nul
if errorlevel 1 (
    echo   NOT INSTALLED. Download from https://git-scm.com/download/win
) else (
    echo   OK
)

echo.
echo [2/3] Checking git's saved user identity (clue you've used GitHub before)...
git config --global user.name 2>nul
git config --global user.email 2>nul
echo   ^(blank above = git not configured yet, fine, we'll set it up^)

echo.
echo [3/3] Checking Python version...
python --version

echo.
echo ===========================================
echo Done. Paste these results to Claude.
echo ===========================================
pause
