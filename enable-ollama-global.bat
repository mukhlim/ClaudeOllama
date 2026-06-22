@echo off
chcp 65001 >nul
title Aktifkan Ollama Cloud Global

echo ===========================================
echo  Aktifkan Ollama Cloud Global
echo ===========================================
echo.

REM Coba jalankan dengan Node.js (prioritas)
where node >nul 2>nul
if %errorlevel% equ 0 (
    node "%~dp0enable-ollama-global.js"
    goto :end
)

REM Fallback ke Bun kalau ada
where bun >nul 2>nul
if %errorlevel% equ 0 (
    bun "%~dp0enable-ollama-global.js"
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
