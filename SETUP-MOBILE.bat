@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo   AETHER Mobile - full setup
echo ==========================================
echo.
echo This will:
echo   1. Verify/install the Python environment
echo   2. Create the HTTPS certificate for your LAN address
echo   3. Build the Android APK (and install it if a phone is connected)
echo   4. Open the firewall port for the phone
echo   5. Start the HTTPS backend the app connects to
echo.
echo Requirements: Python 3.11+, JDK 17+, Android SDK (for the APK build),
echo and your phone on the same Wi-Fi as this PC.
echo.

where powershell >nul 2>nul
if errorlevel 1 (
    echo [FAIL] PowerShell not found. This setup requires Windows PowerShell 5.1+.
    pause
    exit /b 1
)

set "EXTRA="
:askinstall
echo Install the APK on a USB-connected phone too? [y/N]
set "answer=N"
set /p answer=
if /i "%answer%"=="y" set "EXTRA=%EXTRA% -Install"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup-mobile.ps1" %EXTRA%
if errorlevel 1 (
    echo.
    echo [FAIL] Mobile setup failed. Review the messages above.
    echo        Common fixes: run INSTALL_AETHER.bat first; install JDK 17 and
    echo        the Android SDK (scripts\setup-android.ps1 -SkipBuild checks them).
    pause
    exit /b 1
)

echo.
echo [OK] Mobile setup finished.
pause
exit /b 0
