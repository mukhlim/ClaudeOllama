@echo off
:: Build script untuk compile Sciter App jadi .exe dengan PyInstaller
:: Jalankan dari root folder repo

echo [Build] Cleaning previous build...
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"

echo [Build] Running PyInstaller...
pyinstaller build.spec --clean --noconfirm

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed!
    pause
    exit /b 1
)

echo.
echo [Build] Success! Output: dist\ClaudeOllamaLauncher.exe
echo.
pause
