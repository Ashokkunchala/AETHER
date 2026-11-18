#Requires -Version 5.1
<#
.SYNOPSIS
    End-to-end HTTPS smoke test: boot uvicorn with TLS, verify /health, tear down.

.DESCRIPTION
    Proves the exact stack the Android app depends on, without touching the
    phone-facing port you may already be using:

      1. Resolves the LAN IP and ensures data\tls has a certificate covering it
         (scripts\generate_https_cert.py via mobile-common.ps1).
      2. Picks a free port starting at -Port (default 8443); if your real
         backend already owns 8443 the test runs on the next free port.
      3. Starts uvicorn app.main_enhanced:app bound to the LAN IP with
         --ssl-certfile/--ssl-keyfile (same flags as scripts\start-mobile.ps1).
      4. Waits for the shared Test-AETHERBackendHealth helper to report 200.
      5. Runs scripts\verify_tls.py --mode endpoint: full TLS handshake with
         the local certificate trusted as the CA (chain + hostname), served
         certificate byte-equality, and GET /health -> {"status": "ok"}.
      6. Stops the test server (unless -KeepRunning) and prints a summary.

    Exit code 0 = smoke test passed, 1 = failed (uvicorn stderr tail shown).

.PARAMETER Port
    Preferred HTTPS port (default 8443). Auto-advances if the port is busy.

.PARAMETER StartupTimeoutSeconds
    How long to wait for uvicorn to become healthy (default 60).

.PARAMETER ForceCert
    Regenerate the certificate even if the current one is still usable.

.PARAMETER KeepRunning
    Leave the verified test server running after a pass (prints its PID).

.EXAMPLE
    .\scripts\https-smoke-test.ps1
    # Boot TLS backend on a free port, verify health + certificate, stop it.

.EXAMPLE
    .\scripts\https-smoke-test.ps1 -Port 9443 -ForceCert
    # Use a different port and mint a fresh certificate first.
#>
[CmdletBinding()]
param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8443,
    [ValidateRange(5, 600)]
    [int]$StartupTimeoutSeconds = 60,
    [switch]$ForceCert,
    [switch]$KeepRunning
)

$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "mobile-common.ps1")

$root = Get-AETHERRepoRoot
$python = Test-AETHERVenv -Root $root

if (-not (Test-Path (Join-Path $root ".env"))) {
    throw ".env missing at $root. Run INSTALL_AETHER.bat or scripts\setup-windows.ps1 first."
}

function Get-FreeTcpPort {
    param(
        [Parameter(Mandatory = $true)][int]$Start,
        [int]$Span = 20,
        # uvicorn binds the specific LAN IP, not 0.0.0.0 - probing IPAddress::Any
        # can succeed while the real bind fails with WSAEADDRINUSE (10048), so
        # probe the exact address the server will bind to.
        [Parameter(Mandatory = $true)][string]$BindAddress
    )
    $bindIp = [System.Net.IPAddress]::Parse($BindAddress)
    for ($candidate = $Start; $candidate -lt ($Start + $Span); $candidate++) {
        $listener = $null
        try {
            $listener = [System.Net.Sockets.TcpListener]::new($bindIp, $candidate)
            $listener.Start()
            return $candidate
        } catch {
            # Port in use - try the next one.
        } finally {
            if ($listener) { $listener.Stop() }
        }
    }
    throw "No free TCP port found on $BindAddress in $Start..$($Start + $Span - 1)."
}

function Write-Tail {
    param([string]$Path, [int]$Lines = 30)
    if (Test-Path -LiteralPath $Path) {
        Write-Host "--- last $Lines lines of $(Split-Path -Leaf $Path) ---" -ForegroundColor DarkGray
        Get-Content -LiteralPath $Path -Tail $Lines | ForEach-Object { Write-Host $_ -ForegroundColor DarkGray }
    }
}

Write-Host ""
Write-Host "AETHER HTTPS smoke test (uvicorn + TLS + /health)" -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan

# ----------------------------------------------------------- 1. network + cert
$lanIp = Get-AETHERLanIPv4
Write-Host "[PASS] LAN IP: $lanIp" -ForegroundColor Green

$certInfo = New-AETHERHttpsCert -LanIp $lanIp -Force:$ForceCert
Write-Host "[PASS] Certificate: $($certInfo.Cert)" -ForegroundColor Green

# ------------------------------------------------------------------ 2. port
$testPort = Get-FreeTcpPort -Start $Port -BindAddress $lanIp
if ($testPort -ne $Port) {
    Write-Host "[WARN] Port $Port is busy; smoke-testing on $testPort instead." -ForegroundColor Yellow
}
$baseUrl = Get-AETHERMobileUrl -LanIp $lanIp -Port $testPort

# ------------------------------------------------------------------ 3. logs
$logDir = Join-Path $env:TEMP "aether-https-smoke"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$outLog = Join-Path $logDir "uvicorn-$testPort.out.log"
$errLog = Join-Path $logDir "uvicorn-$testPort.err.log"
Remove-Item -LiteralPath $outLog, $errLog -Force -ErrorAction SilentlyContinue

# ---------------------------------------------------------------- 4. start it
$sslArgs = @(
    "-m", "uvicorn", "app.main_enhanced:app",
    "--host", $lanIp,
    "--port", "$testPort",
    "--ssl-certfile", $certInfo.Cert,
    "--ssl-keyfile", $certInfo.Key,
    "--log-level", "info"
)

$server = $null
$failed = $false
$failMessage = ""

# Start-Process joins -ArgumentList with bare spaces, which splits any value
# containing spaces (the repo path often does). Quote every argument that
# needs it and pass a single pre-joined command line instead.
$argLine = ($sslArgs | ForEach-Object {
        if ($_ -match '[\s"]') { '"' + ($_ -replace '"', '\"') + '"' } else { $_ }
    }) -join ' '

Write-Host "Starting uvicorn with TLS at $baseUrl ..." -ForegroundColor Cyan
try {
    $server = Start-Process -FilePath $python `
        -ArgumentList $argLine `
        -WorkingDirectory $root `
        -RedirectStandardOutput $outLog `
        -RedirectStandardError $errLog `
        -PassThru -NoNewWindow

    # ------------------------------------------------------ 5. wait for health
    $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    $healthy = $false
    while ($stopwatch.Elapsed.TotalSeconds -lt $StartupTimeoutSeconds) {
        if ($server.HasExited) { break }
        if (Test-AETHERBackendHealth -Url $baseUrl -TimeoutSeconds 2) {
            $healthy = $true
            break
        }
        Start-Sleep -Milliseconds 750
    }

    if (-not $healthy) {
        if ($server.HasExited) {
            $server.WaitForExit()
            throw "uvicorn exited early with code $($server.ExitCode) before becoming healthy."
        }
        throw "Backend did not become healthy within $StartupTimeoutSeconds s at $baseUrl."
    }
    $elapsed = [math]::Round($stopwatch.Elapsed.TotalSeconds, 1)
    Write-Host "[PASS] Test-AETHERBackendHealth: $baseUrl/health -> 200 (${elapsed}s)" -ForegroundColor Green

    # ------------------------------------------- 6. TLS + JSON verification
    $verifier = Join-Path $root "scripts\verify_tls.py"
    if (-not (Test-Path -LiteralPath $verifier)) {
        throw "Missing $verifier."
    }
    $verifyArgs = @(
        $verifier, "--mode", "endpoint",
        "--host", $lanIp,
        "--port", "$testPort",
        "--cert", $certInfo.Cert
    )
    Invoke-NativeMerged { & $python @verifyArgs 2>&1 } | ForEach-Object { Write-Host $_ }
    if ($LASTEXITCODE -ne 0) {
        throw "verify_tls.py endpoint checks failed (exit $LASTEXITCODE)."
    }
    Write-Host "[PASS] TLS chain + hostname + served-cert match + /health JSON" -ForegroundColor Green
} catch {
    $failed = $true
    $failMessage = $_.Exception.Message
    Write-Host "[FAIL] $failMessage" -ForegroundColor Red
    Write-Tail -Path $errLog
    Write-Tail -Path $outLog -Lines 10
} finally {
    if ($server -and -not $server.HasExited) {
        if ($KeepRunning -and -not $failed) {
            Write-Host ""
            Write-Host "[INFO] -KeepRunning: test server left up at $baseUrl (PID $($server.Id))." -ForegroundColor Yellow
            Write-Host "       Stop it with: Stop-Process -Id $($server.Id)" -ForegroundColor Yellow
        } else {
            Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue
            [void]$server.WaitForExit(10000)
        }
    }
}

Write-Host ""
if ($failed) {
    Write-Host "HTTPS smoke test FAILED: $failMessage" -ForegroundColor Red
    exit 1
}
Write-Host "HTTPS smoke test PASSED: $baseUrl served TLS and healthy /health." -ForegroundColor Green
exit 0
