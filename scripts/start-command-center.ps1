#Requires -Version 5.1
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "AETHER environment missing. Run INSTALL-AETHER.ps1 first."
}
Push-Location $root
try {
    & $pythonExe (Join-Path $root "aether_cli.py") command-center
    if ($LASTEXITCODE -ne 0) {
        Write-Host "AETHER command centre exited with code $LASTEXITCODE." -ForegroundColor Yellow
        exit $LASTEXITCODE
    }
} finally {
    Pop-Location
}
