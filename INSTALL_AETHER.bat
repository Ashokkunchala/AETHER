@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo   AETHER Personal AI - Windows install
echo ==========================================
echo.
echo This will:
echo   1. Check for Python 3.11+ (install via winget if missing is NOT done here)
echo   2. Create .venv and install dependencies
echo   3. Create .env with random secrets (asks for your Gemini API key)
echo   4. Run "aether doctor" to verify the install
echo.

where powershell >nul 2>nul
if errorlevel 1 (
    echo [FAIL] PowerShell not found. This installer requires Windows PowerShell 5.1+.
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup-windows.ps1"
if errorlevel 1 (
    echo.
    echo [FAIL] Installation failed. Review the messages above.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo   Installation complete
echo ==========================================
echo.
echo Start AETHER now? [Y/n]
set "answer=Y"
set /p answer=
if /i "%answer%"=="n" goto :skipstart

echo.
echo Starting AETHER (close this window or press Ctrl+C to stop)...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-windows.ps1"
goto :end

:skipstart
echo.
echo Start it later by double-clicking START-AETHER.bat

:end
echo.
pause
exit /b 0
