@echo off
title DropShip Pro - Stopping...
echo.
echo   Stopping DropShip Pro...

for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" 2^>nul') do (
    taskkill /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3000" 2^>nul') do (
    taskkill /F /PID %%a >nul 2>&1
)

echo   Stopped. Goodbye!
timeout /t 2 /nobreak >nul
