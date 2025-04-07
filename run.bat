@echo off
setlocal enabledelayedexpansion

echo ========================================================
echo                     TournamentBot
echo ========================================================
echo.
echo Starting initialization...

REM Set PYTHONPATH to include the current directory for proper imports
set PYTHONPATH=%PYTHONPATH%;%CD%
echo Python path set to: %PYTHONPATH%

REM Check if Python is installed
echo Checking Python installation...
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Python not found. Please install Python and try again.
    goto :error
)

REM Check for dependencies
echo Checking dependencies...
python -c "import discord, aiosqlite, dotenv" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: Some dependencies may be missing.
    echo Run the following command to install required packages:
    echo pip install -r requirements.txt
    echo.
    set /p continue="Do you want to continue anyway? (y/n): "
    if /i "!continue!" NEQ "y" goto :error
)

echo.
echo ========================================================
echo                 Starting TournamentBot
echo ========================================================
echo.
python Scripts\TournamentBot\main.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Bot exited with an error. Check the logs above for details.
    goto :error
) else (
    echo.
    echo Bot exited successfully.
    goto :end
)

:error
echo.
echo ========================================================
echo                     TROUBLESHOOTING
echo ========================================================
echo.
echo If you encountered errors, try these steps:
echo.
echo 1. Make sure you've installed all required dependencies:
echo    pip install -r requirements.txt
echo.
echo 2. If imports are failing, verify the PYTHONPATH is set correctly.
echo.
echo 3. For more detailed logs, check bot.log in the current directory.
echo.
pause
exit /b 1

:end
echo.
echo Thank you for using TournamentBot!
echo.
pause
exit /b 0