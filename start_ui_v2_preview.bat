@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 "preview\launch_isolated.py"
) else (
    python "preview\launch_isolated.py"
)
if errorlevel 1 (
    echo.
    echo Preview failed. Python 3 is required.
    pause
)
