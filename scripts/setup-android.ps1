#Requires -Version 5.1
<#
.SYNOPSIS
    Set up and build the JARVIS Android app on this Windows machine.

.DESCRIPTION
    Checks the prerequisites (JDK 17+, Android SDK with platform 35 and
    build-tools 35.0.0), writes android\local.properties when the SDK location
    is known, then builds the debug APK with the checked-in Gradle wrapper.

    With -Install and a device connected over USB/wireless debugging, the APK is
    installed on the device with adb.

.PARAMETER Install
    After a successful build, install the APK on the first connected device.

.PARAMETER Reinstall
    With -Install, uninstall the existing app first (keeps no app data).

.PARAMETER SkipBuild
    Only run the prerequisite checks; do not invoke Gradle.

.PARAMETER SdkRoot
    Android SDK location. Defaults to $env:ANDROID_HOME, then
    $env:ANDROID_SDK_ROOT, then %LOCALAPPDATA%\Android\Sdk, then an existing
    android\local.properties value.

.EXAMPLE
    .\scripts\setup-android.ps1
    # Check prerequisites and build app-debug.apk.

.EXAMPLE
    .\scripts\setup-android.ps1 -Install
    # Build and install on a connected device.
#>
[CmdletBinding()]
param(
    [switch]$Install,
    [switch]$Reinstall,
    [switch]$SkipBuild,
    [string]$SdkRoot = ""
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$AndroidDir = Join-Path $RepoRoot "android"
$GradleBat = Join-Path $AndroidDir "gradlew.bat"
$LocalProps = Join-Path $AndroidDir "local.properties"
$ApkPath = Join-Path $AndroidDir "app\build\outputs\apk\debug\app-debug.apk"
$PackageName = "com.ashok.jarvis"

if (-not (Test-Path (Join-Path $AndroidDir "settings.gradle.kts"))) {
    throw "Run this script from the Jarvis-Personal-AI repository (expected android\settings.gradle.kts)."
}

Write-Host ""
Write-Host "JARVIS Personal AI - Android setup" -ForegroundColor Cyan
Write-Host "===================================" -ForegroundColor Cyan

function Fail([string]$Message) {
    Write-Host "[FAIL] $Message" -ForegroundColor Red
    exit 1
}
function Pass([string]$Message) { Write-Host "[PASS] $Message" -ForegroundColor Green }
function Warn([string]$Message) { Write-Host "[WARN] $Message" -ForegroundColor Yellow }

# Run a native command that writes to stderr (sdkmanager, adb, java) with 2>&1
# redirection. Under $ErrorActionPreference = 'Stop', PS 5.1 turns native stderr
# into a terminating NativeCommandError; Continue lets it flow as output instead.
function Invoke-NativeMerged {
    param([scriptblock]$Block)
    $eap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try { & $Block } finally { $ErrorActionPreference = $eap }
}

# ------------------------------------------------------------------- 1. JDK 17
$javaExe = $null
if ($env:JAVA_HOME) {
    $candidate = Join-Path $env:JAVA_HOME "bin\java.exe"
    if (Test-Path -LiteralPath $candidate) { $javaExe = $candidate }
}
if (-not $javaExe) {
    $javaCommand = Get-Command java -CommandType Application -ErrorAction SilentlyContinue
    if ($javaCommand) { $javaExe = $javaCommand.Source }
}
if (-not $javaExe) {
    Fail "JDK 17+ not found. Install Microsoft OpenJDK 17 (winget install Microsoft.OpenJDK.17) or Android Studio, then reopen PowerShell."
}

$javaVersion = ""
try {
    # java -version writes to stderr; let cmd merge the streams first so the
    # raw text is easy to match (Invoke-NativeMerged would add error formatting).
    $versionOutput = (& cmd /c "`"$javaExe`" -version 2>&1" | Out-String)
    if ($versionOutput -match '"(\d+)(?:\.(\d+))?') {
        $major = [int]$Matches[1]
        $minor = if ($Matches[2]) { [int]$Matches[2] } else { 0 }
        # JDK 9+ reports the real major version; JDK 8 would report 1.8.
        if ($major -eq 1 -and $minor -gt 0) { $javaVersion = "$major.$minor" } else { $javaVersion = "$major" }
    }
} catch { }
if (-not $javaVersion) { Fail "Could not determine the Java version from: $javaExe" }
$javaMajor = [int]($javaVersion -split '\.')[0]
if ($javaMajor -lt 17) {
    Fail "Java $javaVersion found at $javaExe, but the app needs JDK 17+. Install Microsoft OpenJDK 17 and set JAVA_HOME."
}
Pass "JDK $javaVersion ($javaExe)"

# ----------------------------------------------------------------- 2. Android SDK
function Get-LocalPropsSdk {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    $line = Get-Content -LiteralPath $Path | Where-Object { $_ -match '^\s*sdk\.dir\s*=' } | Select-Object -Last 1
    if ($line -and $line -match '^\s*sdk\.dir\s*=\s*(.+)$') {
        return $Matches[1].Trim().Replace('\', '/')
    }
    return $null
}

if ([string]::IsNullOrWhiteSpace($SdkRoot)) {
    if ($env:ANDROID_HOME -and (Test-Path -LiteralPath $env:ANDROID_HOME)) { $SdkRoot = $env:ANDROID_HOME }
    elseif ($env:ANDROID_SDK_ROOT -and (Test-Path -LiteralPath $env:ANDROID_SDK_ROOT)) { $SdkRoot = $env:ANDROID_SDK_ROOT }
    else {
        $defaultSdk = Join-Path $env:LOCALAPPDATA "Android\Sdk"
        if (Test-Path -LiteralPath $defaultSdk) { $SdkRoot = $defaultSdk }
        else {
            $fromProps = Get-LocalPropsSdk -Path $LocalProps
            if ($fromProps) { $SdkRoot = $fromProps }
        }
    }
}

if (-not $SdkRoot -or -not (Test-Path -LiteralPath $SdkRoot)) {
    Fail @"
Android SDK not found. Install it with either:
  - Android Studio (https://developer.android.com/studio), then reopen this script, or
  - command line tools: winget install Google.AndroidCommandLineTools, then run sdkmanager from the extracted folder.
Then set ANDROID_HOME or pass -SdkRoot 'C:\path\to\Android\Sdk'.
"@
}
$SdkRoot = (Resolve-Path -LiteralPath $SdkRoot).Path
Pass "Android SDK: $SdkRoot"

# Required packages: platform 35 + build-tools 35.0.0 (see android/app/build.gradle.kts).
$platformDir = Join-Path $SdkRoot "platforms\android-35"
$buildToolsDir = Join-Path $SdkRoot "build-tools\35.0.0"
$missing = @()
if (-not (Test-Path -LiteralPath $platformDir)) { $missing += "platforms;android-35" }
if (-not (Test-Path -LiteralPath $buildToolsDir)) { $missing += "build-tools;35.0.0" }

if ($missing.Count -gt 0) {
    $sdkmanager = Get-ChildItem -Path (Join-Path $SdkRoot "cmdline-tools") -Filter "sdkmanager.bat" -Recurse -ErrorAction SilentlyContinue |
        Select-Object -First 1 -ExpandProperty FullName
    if ($sdkmanager) {
        Write-Host "Installing missing SDK packages: $($missing -join ', ')..." -ForegroundColor Yellow
        foreach ($package in $missing) {
            Invoke-NativeMerged { & $sdkmanager --install $package --sdk_root="$SdkRoot" 2>&1 } | Out-Null
            if ($LASTEXITCODE -ne 0) { Fail "sdkmanager failed to install $package. Run it manually and retry." }
        }
        Pass "Installed: $($missing -join ', ')"
    } else {
        Fail "Missing SDK packages: $($missing -join ', '), and sdkmanager was not found under $SdkRoot\cmdline-tools. Open Android Studio > Settings > SDK Manager and install them, then rerun."
    }
} else {
    Pass "SDK packages present (platforms;android-35, build-tools;35.0.0)"
}

# ------------------------------------------------------- 3. local.properties
$propsSdk = Get-LocalPropsSdk -Path $LocalProps
$normalizedSdk = $SdkRoot -replace '\\', '/'
if ($propsSdk -ne $normalizedSdk) {
    # Never commit local.properties; it is machine-specific (and gitignored).
    Set-Content -LiteralPath $LocalProps -Value "sdk.dir=$normalizedSdk" -Encoding ASCII
    Write-Host "Wrote android\local.properties (sdk.dir=$normalizedSdk)." -ForegroundColor DarkGray
}

# ------------------------------------------------------------- 4. build (or not)
if ($SkipBuild) {
    Write-Host ""
    Write-Host "Prerequisite checks complete (-SkipBuild: no build invoked)." -ForegroundColor Green
    exit 0
}

if (-not (Test-Path -LiteralPath $GradleBat)) {
    Fail "Missing $GradleBat. The Gradle wrapper scripts should be checked in; restore them with: git checkout -- android/gradlew.bat android/gradlew"
}
if (-not (Test-Path -LiteralPath (Join-Path $AndroidDir "gradle\wrapper\gradle-wrapper.jar"))) {
    Fail "Missing android\gradle\wrapper\gradle-wrapper.jar (needed by gradlew to download Gradle). If this is a fresh clone, copy it from another checkout or run: gradle wrapper --gradle-version 8.9 (inside android\)."
}

Write-Host ""
Write-Host "Building debug APK (first run downloads Gradle 8.9 and dependencies)..." -ForegroundColor Cyan
& $GradleBat -p $AndroidDir assembleDebug --no-daemon
if ($LASTEXITCODE -ne 0) {
    Fail "Gradle build failed. Review the output above. Common fixes: JDK 17 on PATH/JAVA_HOME, stable network for dependency downloads, enough disk space."
}
if (-not (Test-Path -LiteralPath $ApkPath)) {
    Fail "Build reported success but the APK was not found at $ApkPath."
}
$apkSize = [math]::Round((Get-Item -LiteralPath $ApkPath).Length / 1MB, 1)
Pass "APK built: $ApkPath ($apkSize MB)"

# ----------------------------------------------------------------- 5. install
if (-not $Install) {
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Green
    Write-Host "  Install on a USB-connected phone: .\scripts\setup-android.ps1 -Install"
    Write-Host "  Or copy the APK to the phone and tap it to install."
    Write-Host "  App id: $PackageName  |  Backend setup: android\README.md"
    exit 0
}

$adb = $null
$adbCandidates = @()
if ($env:ANDROID_HOME) { $adbCandidates += (Join-Path $env:ANDROID_HOME "platform-tools\adb.exe") }
if ($env:ANDROID_SDK_ROOT) { $adbCandidates += (Join-Path $env:ANDROID_SDK_ROOT "platform-tools\adb.exe") }
$adbCandidates += (Join-Path $SdkRoot "platform-tools\adb.exe")
$adbCommand = Get-Command adb -CommandType Application -ErrorAction SilentlyContinue
if ($adbCommand) { $adbCandidates += $adbCommand.Source }
foreach ($candidate in $adbCandidates) {
    if ($candidate -and (Test-Path -LiteralPath $candidate)) { $adb = $candidate; break }
}
if (-not $adb) {
    Fail "adb not found. Install platform-tools (it is installed with the SDK checks above) or add platform-tools to PATH."
}

& $adb start-server | Out-Null
$deviceLines = @(& $adb devices | Select-String -Pattern "^\S+\s+device\s*$")
if ($deviceLines.Count -eq 0) {
    Fail "No Android device connected. Enable Developer options > USB debugging, plug the phone in, accept the RSA prompt, then rerun with -Install. (Wireless debugging also works: jarvis android setup)."
}
if ($deviceLines.Count -gt 1) {
    Warn "Multiple devices connected; installing on the first one."
}
$deviceId = ($deviceLines[0].Line -split "\s+")[0]
Pass "Device connected: $deviceId"

if ($Reinstall) {
    # Absence of the app is fine; ignore the uninstall result.
    Invoke-NativeMerged { & $adb uninstall $PackageName 2>&1 } | Out-Null
}

$installOutput = (Invoke-NativeMerged { & $adb install -r $ApkPath 2>&1 } | Out-String)
if ($LASTEXITCODE -ne 0 -or $installOutput -notmatch "Success") {
    Fail "adb install failed: $installOutput"
}
Pass "Installed $PackageName on the device."

Write-Host ""
Write-Host "Launch JARVIS from the app drawer, then follow android\README.md to pair with your backend over HTTPS." -ForegroundColor Green
