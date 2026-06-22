#!/usr/bin/env pwsh
# Launcher PowerShell untuk Sciter Desktop App (Claude + Ollama Cloud)
# Jalankan ini dari root folder repo — terminal auto-close setelah app terbuka

$AppDir = $PSScriptRoot
$env:PATH = "$AppDir\sciter-app;$env:PATH"

# Coba pythonw dulu (tanpa console window)
$pythonw = (Get-Command pythonw -ErrorAction SilentlyContinue)?.Source
if (-not $pythonw) {
    $pythonw = "C:\Program Files\Python314\pythonw.exe"
}
if (Test-Path $pythonw) {
    Start-Process $pythonw -ArgumentList "$AppDir\sciter-app\sciter_app.py" -WindowStyle Hidden
} else {
    Start-Process python -ArgumentList "$AppDir\sciter-app\sciter_app.py" -WindowStyle Hidden
}
