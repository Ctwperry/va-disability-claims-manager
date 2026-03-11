@echo off
:: VA Disability Claims Manager — Windows Launcher
:: Double-click this file to start the application

set PYTHON=C:\Users\Ctwpe\AppData\Local\Programs\Python\Python314\python.exe
set APP_DIR=%~dp0

if not exist "%PYTHON%" (
    echo Python not found at: %PYTHON%
    echo Please install Python 3.14 from python.org
    pause
    exit /b 1
)

cd /d "%APP_DIR%"
"%PYTHON%" main.py
if errorlevel 1 (
    echo.
    echo Application exited with an error.
    pause
)
