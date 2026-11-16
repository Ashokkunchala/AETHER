@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo   AETHER Personal AI - start
echo ==========================================
echo.

if not exist "%~dp0.venv\Scripts\python.exe" (
    echo [FAIL] Not installed yet. Double-click INSTALL_JARVIS.bat first.
    pause
    exit /b 1
)
if not exist "%~dp0.env" (
    echo [FAIL] .env not found. Double-click INSTALL_JARVIS.bat first.
    pause
    exit /b 1
)

echo Starting backend on http://127.0.0.1:8000 ...
echo Open http://127.0.0.1:8000 in your browser once it says "Uvicorn running".
echo Close this window or press Ctrl+C to stop AETHER.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-windows.ps1"
if errorlevel 1 (
    echo.
    echo [FAIL] AETHER failed to start. Check the messages above.
    pause
    exit /b 1
)
exit /b 0
