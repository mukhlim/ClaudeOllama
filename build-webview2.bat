@echo off
:: Build script untuk compile WebView2 App jadi .exe dengan PyInstaller
:: Jalankan dari root folder repo

echo [Build] Cleaning previous build...
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"

echo [Build] Running PyInstaller...
pyinstaller webview2-build.spec --clean --noconfirm

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed!
    pause
    exit /b 1
)

echo.
echo [Build] Copying sidecar files to dist...
if exist "webview2-app\workspaces.json" (
    copy /Y "webview2-app\workspaces.json" "dist\" >nul
    echo [Build] copied workspaces.json
) else (
    echo {"current": ".", "recent": []} > "dist\workspaces.json"
    echo [Build] created default workspaces.json
)
if exist "config.json" (
    copy /Y "config.json" "dist\" >nul
    echo [Build] copied config.json
)

echo.
echo [Build] Success! Output: dist\ClaudeOllamaLauncher.exe
echo.
pause
