@echo off
chcp 65001 >nul
title Cek Environment Variables Ollama Cloud

echo ===========================================
echo  Cek Environment Variables Ollama Cloud
echo ===========================================
echo.

where node >nul 2>nul
if %errorlevel% equ 0 (
    node "%~dp0check-env-ollama.js"
    goto :end
)

where bun >nul 2>nul
if %errorlevel% equ 0 (
    bun "%~dp0check-env-ollama.js"
    goto :end
)

echo [ERROR] Node.js dan Bun tidak ditemukan di PATH.
echo         Download Node.js: https://nodejs.org
echo         Download Bun:     https://bun.sh
echo.
pause
exit /b 1

:end
echo.
pause
