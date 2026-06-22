@echo off
chcp 65001 >nul
title Nonaktifkan Ollama Cloud Global

echo ===========================================
echo  Nonaktifkan Ollama Cloud Global
echo ===========================================
echo.

where node >nul 2>nul
if %errorlevel% equ 0 (
    node "%~dp0disable-ollama-global.js"
    goto :end
)

where bun >nul 2>nul
if %errorlevel% equ 0 (
    bun "%~dp0disable-ollama-global.js"
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
