#Requires -Version 5.1
<#
.SYNOPSIS
    Start the AETHER HTTP backend for the browser UI on http://127.0.0.1:8000.

.DESCRIPTION
    Idempotent launcher used by START-AETHER.bat:

      1. Verifies .venv\Scripts\python.exe and .env exist (clear error if not).
      2. If a healthy AETHER already answers on the requested URL, reports the
         owning PID and exits 0 instead of crashing with WSAEADDRINUSE (10048).
      3. If the port is held by something else, names the process/PID and prints
         the exact Stop-Process command instead of a raw socket error.
      4. Otherwise starts uvicorn (app.main_enhanced:app) bound to 127.0.0.1 and
         propagates its exit code, so a failed start is never reported as success.

    Binding stays on loopback on purpose. For the phone-facing HTTPS listener
    use scripts\start-mobile.ps1 (private LAN over TLS).

.PARAMETER Port
    TCP port for the browser backend (default 8000).

.PARAMETER BindAddress
    Local address to bind. Loopback only (default 127.0.0.1); 0.0.0.0 is
    refused because this prototype must never be reachable beyond this machine.

.EXAMPLE
    .\scripts\start-windows.ps1
    # Start (or report the already running) backend on 127.0.0.1:8000.

.EXAMPLE
    .\scripts\start-windows.ps1 -Port 8001
    # Port 8000 busy with a foreign process: run on the next port instead.
#>
[CmdletBinding()]
param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8000,
    [string]$BindAddress = "127.0.0.1"
)

$ErrorActionPreference = "Stop"

if ($BindAddress -in @("0.0.0.0", "::", "[::]")) {
    Write-Host "[FAIL] Refusing to bind $BindAddress - the browser backend stays on loopback." -ForegroundColor Red
    Write-Host "       For the phone-facing LAN listener use: .\scripts\start-mobile.ps1 (HTTPS)." -ForegroundColor Yellow
    exit 1
}

$root = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $root ".venv\Scripts\python.exe"
$envFile = Join-Path $root ".env"

if (-not (Test-Path -LiteralPath $pythonExe)) {
    Write-Host "Virtual environment not found. Run: .\scripts\setup-windows.ps1 (or INSTALL_AETHER.bat)" -ForegroundColor Yellow
    exit 1
}
if (-not (Test-Path -LiteralPath $envFile)) {
    Write-Host ".env not found. Run setup and add your Gemini API key." -ForegroundColor Yellow
    exit 1
}

$baseUrl = "http://${BindAddress}:$Port"

function Test-AETHERHealthEndpoint {
    param([Parameter(Mandatory = $true)][string]$Url)
    # Plain HTTP, no TLS involved - a plain Invoke-WebRequest is enough.
    try {
        $response = Invoke-WebRequest -Uri "$Url/health" -TimeoutSec 3 -UseBasicParsing
        return ($response.StatusCode -eq 200 -and $response.Content -match 'aether')
    } catch {
        return $false
    }
}

function Get-TcpListenerProcessId {
    param([Parameter(Mandatory = $true)][int]$PortNumber)
    try {
        $connection = Get-NetTCPConnection -LocalPort $PortNumber -State Listen -ErrorAction Stop |
            Select-Object -First 1
        if ($connection) { return [int]$connection.OwningProcess }
    } catch { }
    # Fallback for hosts without the NetTCPIP module.
    try {
        $line = netstat -ano | Where-Object { $_ -match ":$PortNumber\s+.*LISTENING" } | Select-Object -First 1
        if ($line) {
            $fields = ($line.Trim() -split '\s+')
            $owner = [int]$fields[-1]
            if ($owner -gt 0) { return $owner }
        }
    } catch { }
    return $null
}

# --------------------------------------------- already running / port conflict
if (Test-AETHERHealthEndpoint -Url $baseUrl) {
    $ownerId = Get-TcpListenerProcessId -PortNumber $Port
    $ownerName = ""
    if ($ownerId) {
        try { $ownerName = ": $((Get-Process -Id $ownerId).ProcessName), started $((Get-Process -Id $ownerId).StartTime.ToString('HH:mm:ss'))" } catch { }
    }
    Write-Host "[PASS] AETHER backend already running at $baseUrl (PID $ownerId$ownerName)" -ForegroundColor Green
    Write-Host "       Open $baseUrl in your browser. To restart it, run:" -ForegroundColor DarkGray
    if ($ownerId) { Write-Host "       Stop-Process -Id $ownerId -Force" -ForegroundColor DarkGray }
    exit 0
}

$busyPid = Get-TcpListenerProcessId -PortNumber $Port
if ($busyPid) {
    $busyName = "unknown"
    $busyPath = ""
    try {
        $busyProcess = Get-Process -Id $busyPid -ErrorAction Stop
        $busyName = $busyProcess.ProcessName
        $busyPath = $busyProcess.Path
    } catch { }
    Write-Host "[FAIL] Port $Port on $BindAddress is used by another program (PID ${busyPid}: $busyName)." -ForegroundColor Red
    if ($busyPath) { Write-Host "       Path: $busyPath" -ForegroundColor DarkGray }
    Write-Host "       It does not answer /health, so it is not a AETHER backend." -ForegroundColor Yellow
    Write-Host "       Free the port with:  Stop-Process -Id $busyPid -Force" -ForegroundColor Yellow
    Write-Host "       Or use another port: .\scripts\start-windows.ps1 -Port $($Port + 1)" -ForegroundColor Yellow
    exit 1
}

# ------------------------------------------------------------------- start it
Write-Host "Starting backend on $baseUrl ..." -ForegroundColor Cyan
Write-Host "Open $baseUrl in your browser once it says 'Uvicorn running'." -ForegroundColor Cyan

Push-Location $root
try {
    # Uvicorn writes its INFO logs to stderr; under $ErrorActionPreference =
    # 'Stop' PowerShell 5.1 turns redirected native stderr into a terminating
    # NativeCommandError, so relax it just for this call.
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $pythonExe -m uvicorn app.main_enhanced:app --host $BindAddress --port $Port
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previous
    }
} finally {
    Pop-Location
}

if ($exitCode -ne 0) {
    Write-Host "[FAIL] uvicorn exited with code $exitCode. Check the output above." -ForegroundColor Red
    exit $exitCode
}
exit 0
