@echo off
title DropShip Pro v4.0
color 0A
cls

:: ── Get root directory (one level up from this script) ────────
set ROOT=%~dp0..

echo.
echo   ========================================
echo     DropShip Pro v4.0 - eBay API Edition
echo   ========================================
echo.

:: ── Check Python ──────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo   [ERROR] Python is not installed or not in PATH.
    echo.
    echo   Please install Python from: https://www.python.org/downloads/
    echo   IMPORTANT: Check "Add Python to PATH" during install!
    echo.
    pause
    exit /b 1
)

:: ── Check Node.js ─────────────────────────────────────────────
node --version >nul 2>&1
if errorlevel 1 (
    echo   [ERROR] Node.js is not installed or not in PATH.
    echo.
    echo   Please install Node.js from: https://nodejs.org  (pick LTS version)
    echo.
    pause
    exit /b 1
)

:: ── Check .env file exists ────────────────────────────────────
if not exist "%ROOT%\backend\.env" (
    echo   [SETUP] Creating .env from template...
    copy "%ROOT%\backend\.env.example" "%ROOT%\backend\.env" >nul
    echo.
    echo   ============================================
    echo    FIRST TIME SETUP - Action Required
    echo   ============================================
    echo.
    echo   A file called .env was created in the backend folder.
    echo   Please open it with Notepad and fill in:
    echo.
    echo     APP_USERNAME  = your chosen username
    echo     APP_PASSWORD  = your chosen password
    echo     APP_SECRET    = any random words here
    echo.
    echo   eBay API keys can be added later from inside the app.
    echo.
    echo   After editing .env, run this file again.
    echo.
    start notepad "%ROOT%\backend\.env"
    pause
    exit /b 0
)

:: ── Kill anything on ports 3000 / 8000 ────────────────────────
echo   Stopping any previous instances...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" 2^>nul') do (
    taskkill /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3000" 2^>nul') do (
    taskkill /F /PID %%a >nul 2>&1
)

:: ── Install Python deps ────────────────────────────────────────
echo   Installing Python packages (first run may take a minute)...
cd /d "%ROOT%\backend"
pip install -q -r requirements.txt
if errorlevel 1 (
    echo   [ERROR] Failed to install Python packages.
    pause
    exit /b 1
)

:: ── Start backend ─────────────────────────────────────────────
echo   Starting backend API on port 8000...
start /B "" uvicorn main:app --host 0.0.0.0 --port 8000 --reload > "%ROOT%\backend.log" 2>&1

:: ── Install frontend deps ──────────────────────────────────────
echo   Installing frontend packages (first run may take a minute)...
cd /d "%ROOT%\frontend"
call npm install --silent
if errorlevel 1 (
    echo   [ERROR] Failed to install frontend packages.
    pause
    exit /b 1
)

:: ── Start frontend ────────────────────────────────────────────
echo   Starting frontend on port 3000...
start /B "" npm run dev > "%ROOT%\frontend.log" 2>&1

:: ── Wait for app to be ready ──────────────────────────────────
echo   Waiting for app to start...
timeout /t 4 /nobreak >nul

:: ── Open browser ──────────────────────────────────────────────
echo.
echo   ========================================
echo     App is running!
echo     Opening http://localhost:3000 ...
echo   ========================================
echo.
echo   Logs: backend.log / frontend.log  (in app root folder)
echo   To stop: run stop.bat or close this window
echo.
start http://localhost:3000

:: ── Keep window open ──────────────────────────────────────────
echo   Press Ctrl+C or close this window to stop the app.
echo.
:loop
timeout /t 60 /nobreak >nul
goto loop
