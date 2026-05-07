@echo off
REM Pre-flight check - verifies Sierra + FUB API connections and field names
REM Just double-click this file. It will keep the window open so you can read results.

cd /d "%~dp0"

echo Checking Python is installed...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: Python is not installed or not on your PATH.
    echo Download from https://www.python.org/downloads/ and check "Add Python to PATH" during install.
    echo.
    pause
    exit /b 1
)

echo Installing requests library if needed...
python -m pip install --quiet requests

echo.
echo Running pre-flight check...
echo ===============================================
python test_connections.py
echo ===============================================
echo.
pause
