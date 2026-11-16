@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo   JARVIS Mobile - start HTTPS backend
echo ==========================================
echo.
echo Serves https://<your-LAN-IP>:8443 for the Android app.
echo This window must stay open while your phone uses JARVIS.
echo Close it or press Ctrl+C to stop.
echo.

if not exist "%~dp0.venv\Scripts\python.exe" (
    echo [FAIL] Not installed yet. Double-click INSTALL_JARVIS.bat first,
    echo        or run SETUP-MOBILE.bat for the full phone setup.
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-mobile.ps1"
if errorlevel 1 (
    echo.
    echo [FAIL] HTTPS backend failed to start. Review the messages above.
    pause
    exit /b 1
)
exit /b 0
