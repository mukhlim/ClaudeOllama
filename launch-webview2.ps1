#!/usr/bin/env pwsh
# Launcher PowerShell untuk WebView2 Desktop App (Claude + Ollama Cloud)
# Jalankan ini dari root folder repo

$AppDir = $PSScriptRoot

# Coba pythonw dulu (tanpa console window)
$pythonw = (Get-Command pythonw -ErrorAction SilentlyContinue)?.Source
if (-not $pythonw) {
    $pythonw = "C:\Program Files\Python314\pythonw.exe"
}
if (Test-Path $pythonw) {
    Start-Process $pythonw -ArgumentList "$AppDir\webview2-app\main.py" -WindowStyle Hidden
} else {
    Start-Process python -ArgumentList "$AppDir\webview2-app\main.py" -WindowStyle Hidden
}
