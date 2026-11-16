#Requires -Version 5.1
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "JARVIS environment missing. Run INSTALL-JARVIS.ps1 first."
}
Push-Location $root
try {
    & $pythonExe (Join-Path $root "jarvis_cli.py") command-center
    if ($LASTEXITCODE -ne 0) {
        Write-Host "JARVIS command centre exited with code $LASTEXITCODE." -ForegroundColor Yellow
        exit $LASTEXITCODE
    }
} finally {
    Pop-Location
}
