@echo off
:: Launcher untuk Sciter Desktop App (Claude + Ollama Cloud)
:: CMD window akan auto-close setelah app terbuka

setlocal
set "APP_DIR=%~dp0"
set "PATH=%APP_DIR%sciter-app;%PATH%"

:: Coba pythonw (no console) dulu, fallback ke python
if exist "%LOCALAPPDATA%\Programs\Python\Python314\pythonw.exe" (
    start "" "%LOCALAPPDATA%\Programs\Python\Python314\pythonw.exe" "%APP_DIR%sciter-app\sciter_app.py"
) else if exist "C:\Program Files\Python314\pythonw.exe" (
    start "" "C:\Program Files\Python314\pythonw.exe" "%APP_DIR%sciter-app\sciter_app.py"
) else (
    start /MIN "" python "%APP_DIR%sciter-app\sciter_app.py"
)
endlocal
