@echo off
REM First-time push to GitHub. Configures git, commits all files, pushes to:
REM https://github.com/mattodunlap/sierra-fub-sync
REM
REM Safe to re-run if it fails partway through. Skips steps that are already done.

cd /d "%~dp0"

echo ===========================================
echo  Push project to GitHub
echo ===========================================
echo.

echo [1/7] Configuring git identity (one-time setup)...
git config --global user.name "Matthew Dunlap"
git config --global user.email "matthew@teamdunlaprealty.com"
echo   Done.

echo.
echo [2/7] Initializing git repo (if not already)...
if not exist ".git" (
    git init
) else (
    echo   Already initialized, skipping.
)

echo.
echo [3/7] Verifying .env is gitignored (we never want to push secrets)...
if exist ".gitignore" (
    findstr /b ".env" .gitignore >nul
    if errorlevel 1 (
        echo   WARNING - .env not in .gitignore! Aborting to avoid leaking secrets.
        echo   Add ".env" as a line in .gitignore and re-run.
        pause
        exit /b 1
    )
    echo   OK - .env is gitignored.
) else (
    echo   ERROR - no .gitignore file. Aborting.
    pause
    exit /b 1
)

echo.
echo [4/7] Staging files...
git add .

echo.
echo [5/7] Committing...
git commit -m "Initial commit - Sierra to FUB auto-login URL sync"

echo.
echo [6/7] Setting up remote and main branch...
git branch -M main
git remote remove origin 2>nul
git remote add origin https://github.com/mattodunlap/sierra-fub-sync.git

echo.
echo [7/7] Pushing to GitHub...
echo   A browser window may pop up to authenticate with GitHub.
echo   Click "Sign in with your browser" if prompted, then authorize Git Credential Manager.
echo.
git push -u origin main

echo.
echo ===========================================
if errorlevel 1 (
    echo  Push failed - read the error above.
) else (
    echo  SUCCESS - your code is on GitHub.
    echo  https://github.com/mattodunlap/sierra-fub-sync
)
echo ===========================================
echo.
pause
