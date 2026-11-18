#Requires -Version 5.1
[CmdletBinding()]
param(
    [switch]$Call,
    [switch]$NoLaptop
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$pythonExe = Join-Path $root ".venv\Scripts\python.exe"
$cli = Join-Path $root "aether_cli.py"

if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "AETHER environment missing at $pythonExe. Run INSTALL-AETHER.ps1 first."
}

$cliArgs = @($cli, "robot")
if ($Call) { $cliArgs += "--call" }
if ($NoLaptop) { $cliArgs += "--no-laptop" }

Write-Host "AETHER floating robot. Press v for a voice call, space to pause, q to quit." -ForegroundColor Cyan
& $pythonExe @cliArgs
$code = $LASTEXITCODE

if ($code -ne 0) {
    Write-Host ""
    Write-Host "AETHER robot exited with code $code. Check .env and the voice stack." -ForegroundColor Yellow
    Read-Host "Press Enter to close"
}
exit $code
