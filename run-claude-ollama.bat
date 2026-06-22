@echo off
chcp 65001 >nul
title Claude Code + Ollama Cloud

echo ===========================================
echo  Claude Code Launcher with Ollama Cloud Backend
echo ===========================================
echo.

REM Coba jalankan dengan Node.js (prioritas)
where node >nul 2>nul
if %errorlevel% equ 0 (
    node "%~dp0run-claude-ollama.js"
    goto :end
)

REM Fallback ke Bun kalau ada
where bun >nul 2>nul
if %errorlevel% equ 0 (
    bun "%~dp0run-claude-ollama.js"
    goto :end
)

echo [ERROR] Node.js dan Bun tidak ditemukan di PATH.
echo         Pastikan salah satu sudah terinstall.
echo         Download Node.js: https://nodejs.org
echo         Download Bun:     https://bun.sh
echo.
pause
exit /b 1

:end
REM Kalau exit dengan error, tahan window supaya bisa dibaca
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Proses berhenti dengan kode %errorlevel%.
    pause
)
