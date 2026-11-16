#Requires -Version 5.1
<#
.SYNOPSIS
    One-shot setup to install and run JARVIS on Windows + Android over the LAN.

.DESCRIPTION
    Prepares everything the phone needs, in order:

      1. Verifies the local Python environment (runs scripts\setup-windows.ps1
         when .venv is missing).
      2. Detects this machine's LAN IP and mints the self-signed HTTPS
         certificate the Android app will trust (data\tls\jarvis-ca.crt).
      3. Builds the debug APK (scripts\setup-android.ps1) and, with -Install,
         pushes it to a USB-connected device over adb.
      4. Adds the inbound firewall rule for the HTTPS port.
      5. Prints the exact phone-side steps (CA install, backend URL, token).

    With -Start (the default when nothing fails) it then hands off to
    scripts\start-mobile.ps1, which serves https://<lan-ip>:8443 until Ctrl+C.

.PARAMETER Install
    Also install the built APK on the first device connected over adb.

.PARAMETER Start
    Start the HTTPS backend after setup (default: on; pass -Start:$false to skip).

.PARAMETER SkipBuild
    Skip the APK build (reuse an existing app-debug.apk).

.PARAMETER Port
    HTTPS port for the phone-facing listener (default 8443).

.PARAMETER ForceCert
    Regenerate the HTTPS certificate even if the current one is valid.

.EXAMPLE
    .\scripts\setup-mobile.ps1 -Install
    # Full setup: cert + APK installed on the phone + HTTPS backend running.

.EXAMPLE
    .\scripts\setup-mobile.ps1 -Start:$false
    # Prepare everything but do not start the server yet.
#>
[CmdletBinding()]
param(
    [switch]$Install,
    [bool]$Start = $true,
    [switch]$SkipBuild,
    [ValidateRange(1, 65535)]
    [int]$Port = 8443,
    [switch]$ForceCert
)

$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "mobile-common.ps1")

$root = Get-JarvisRepoRoot

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "JARVIS Mobile - complete setup (Windows + Android over LAN)" -ForegroundColor Cyan
Write-Host "=============================================================" -ForegroundColor Cyan
Write-Host "Repository: $root"

# ------------------------------------------------------------ 1. python env
Write-Step "Step 1/5: Python environment"
$python = $null
try { $python = Test-JarvisVenv -Root $root } catch {
    Write-Host ".venv missing - running scripts\setup-windows.ps1 first..." -ForegroundColor Yellow
    & (Join-Path $root "scripts\setup-windows.ps1") -SkipVerify
    if ($LASTEXITCODE -ne 0) { throw "scripts\setup-windows.ps1 failed (exit $LASTEXITCODE)." }
    $python = Test-JarvisVenv -Root $root
}
Write-Host "[PASS] $python" -ForegroundColor Green

if (-not (Test-Path (Join-Path $root ".env"))) {
    throw ".env missing. Run scripts\setup-windows.ps1 (it creates .env) and set your API keys."
}

# ------------------------------------------------------- 2. HTTPS certificate
Write-Step "Step 2/5: LAN address + HTTPS certificate"
$lanIp = Get-JarvisLanIPv4
Write-Host "[PASS] LAN IP: $lanIp" -ForegroundColor Green
$certInfo = New-JarvisHttpsCert -LanIp $lanIp -Force:$ForceCert
Write-Host "[PASS] Certificate ready: $($certInfo.Cert)" -ForegroundColor Green
Write-Host "       Phone CA file:     $($certInfo.CaCopy)" -ForegroundColor Green
$baseUrl = Get-JarvisMobileUrl -LanIp $lanIp -Port $Port

# ------------------------------------------------------------------- 3. APK
Write-Step "Step 3/5: Android APK"
$apkPath = Join-Path $root "android\app\build\outputs\apk\debug\app-debug.apk"
if ($SkipBuild -and (Test-Path -LiteralPath $apkPath)) {
    Write-Host "[PASS] Reusing existing APK: $apkPath" -ForegroundColor Green
} else {
    $androidArgs = @()
    if ($Install) { $androidArgs += "-Install" }
    & (Join-Path $root "scripts\setup-android.ps1") @androidArgs
    if ($LASTEXITCODE -ne 0) { throw "scripts\setup-android.ps1 failed (exit $LASTEXITCODE)." }
}
if (-not (Test-Path -LiteralPath $apkPath)) {
    throw "APK not found at $apkPath after the build step."
}
Write-Host "[PASS] APK: $apkPath" -ForegroundColor Green

# ---------------------------------------------------------------- 4. firewall
Write-Step "Step 4/5: Firewall rule for TCP $Port"
Add-JarvisFirewallRule -Port $Port | Out-Null

# --------------------------------------------------------------- 5. summary
Write-Step "Step 5/5: What to do on the phone"
$token = Read-JarvisEnvValue -Name "JARVIS_API_TOKEN"
Write-Host "  Backend URL   : $baseUrl" -ForegroundColor White
if ($token) {
    Write-Host "  Pairing token : $token" -ForegroundColor White
} else {
    Write-Host "  Pairing token : MISSING - set JARVIS_API_TOKEN (32+ chars) in .env" -ForegroundColor Yellow
}
Write-Host ""
Write-Host "  a. Install the APK on the phone:" -ForegroundColor Green
Write-Host "     - USB: rerun with -Install, or"
Write-Host "     - Copy $apkPath to the phone and tap it."
Write-Host "  b. One-time CA install (required for HTTPS):" -ForegroundColor Green
Write-Host "     - Send $($certInfo.CaCopy) to the phone (USB/Bluetooth/Drive)."
Write-Host "     - Settings > Security > Encryption & credentials > Install a certificate"
Write-Host "       > CA certificate > select jarvis-ca.crt."
Write-Host "  c. In the app: paste the backend URL and pairing token above," -ForegroundColor Green
Write-Host "     tap Pair device, then Connect securely."
Write-Host ""
Write-Host "  Keep this Windows account signed in and this machine on the same Wi-Fi" -ForegroundColor DarkGray
Write-Host "  as the phone whenever you want JARVIS reachable. Never port-forward $Port" -ForegroundColor DarkGray
Write-Host "  to the internet; this prototype is private-LAN only." -ForegroundColor DarkGray

# ------------------------------------------------------------------ start it
if ($Start) {
    Write-Host ""
    Write-Host "Starting the HTTPS backend (this window stays open; Ctrl+C stops it)..." -ForegroundColor Cyan
    & (Join-Path $root "scripts\start-mobile.ps1") -Port $Port -ForceCert:$ForceCert
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "Setup complete. Start the backend later with: .\scripts\start-mobile.ps1" -ForegroundColor Green
exit 0
