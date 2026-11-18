#Requires -Version 5.1
[CmdletBinding()]
param(
    [switch]$Remove,
    [string]$Hotkey = "CTRL+ALT+A",
    [string]$Name = "AETHER Command Center.lnk"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $root ".venv\Scripts\python.exe"
$launcher = Join-Path $PSScriptRoot "start-command-center.ps1"
$programs = [Environment]::GetFolderPath("Programs")
$folder = Join-Path $programs "AETHER"
$linkPath = Join-Path $folder $Name

if ($Remove) {
    if (Test-Path -LiteralPath $linkPath) {
        Remove-Item -LiteralPath $linkPath -Force
        Write-Host "Removed global AETHER shortcut: $linkPath" -ForegroundColor Green
    } else {
        Write-Host "AETHER global shortcut is not installed." -ForegroundColor Yellow
    }
    return
}
if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "AETHER Python environment not found. Run INSTALL-AETHER.ps1 first."
}
if (-not (Test-Path -LiteralPath $launcher)) {
    throw "Missing command-centre launcher: $launcher"
}
New-Item -ItemType Directory -Force -Path $folder | Out-Null
$powershell = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$ws = New-Object -ComObject WScript.Shell
$shortcut = $ws.CreateShortcut($linkPath)
$shortcut.TargetPath = $powershell
$shortcut.Arguments = '-NoProfile -ExecutionPolicy Bypass -File "' + $launcher + '"'
$shortcut.WorkingDirectory = $root
$shortcut.Hotkey = $Hotkey
$shortcut.Description = "Open the AETHER cinematic terminal command centre"
$shortcut.WindowStyle = 1
$shortcut.Save()

Write-Host "Installed AETHER global shortcut." -ForegroundColor Green
Write-Host "Hotkey: $Hotkey" -ForegroundColor Cyan
Write-Host "Start Menu: $linkPath" -ForegroundColor DarkGray
Write-Host "Remove with: .\scripts\install-global-hotkey.ps1 -Remove" -ForegroundColor DarkGray
