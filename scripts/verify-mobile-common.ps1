#Requires -Version 5.1
<#
.SYNOPSIS
    Verify the shared mobile helpers in scripts\mobile-common.ps1.

.DESCRIPTION
    Exercises every helper that scripts\setup-mobile.ps1 and
    scripts\start-mobile.ps1 depend on, without starting a server:

      1. Get-JarvisRepoRoot      - resolves the repository root
      2. Get-JarvisLanIPv4       - returns a real (non-loopback) LAN address
      3. Test-JarvisVenv         - .venv\Scripts\python.exe exists
      4. Read-JarvisEnvValue     - JARVIS_API_TOKEN present, 32+ chars, not a placeholder
      5. New-JarvisHttpsCert     - data\tls certificate files exist and pass
                                   scripts\verify_tls.py --mode local (CA:TRUE,
                                   >= 7 days validity, SAN covers the LAN IP)
      6. Get-JarvisMobileUrl     - https://<lan-ip>:8443
      7. Test-JarvisBackendHealth - returns a boolean for both a dead endpoint
                                   ($false) and never throws

    Prints [PASS]/[FAIL] per check. Exit code 0 = all checks passed, 1 = failures.

.EXAMPLE
    .\scripts\verify-mobile-common.ps1
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "mobile-common.ps1")

$script:Failures = 0

function Write-Check {
    param(
        [string]$Name,
        [bool]$Ok,
        [string]$Detail = ""
    )
    $suffix = if ($Detail) { " - $Detail" } else { "" }
    if ($Ok) {
        Write-Host "[PASS] $Name$suffix" -ForegroundColor Green
    } else {
        Write-Host "[FAIL] $Name$suffix" -ForegroundColor Red
        $script:Failures++
    }
}

Write-Host ""
Write-Host "JARVIS mobile-common.ps1 helper verification" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan

# --------------------------------------------------------------- 1. repo root
$root = Get-JarvisRepoRoot
$rootOk = $root -and (Test-Path -LiteralPath (Join-Path $root "app\main_enhanced.py")) -and
    (Test-Path -LiteralPath (Join-Path $root "scripts\mobile-common.ps1"))
Write-Check "Get-JarvisRepoRoot" ([bool]$rootOk) $root

# ----------------------------------------------------------------- 2. LAN IP
$lanIp = $null
try { $lanIp = Get-JarvisLanIPv4 } catch { Write-Check "Get-JarvisLanIPv4" $false $_.Exception.Message }
if ($lanIp) {
    $parsed = $null
    $isIp = [System.Net.IPAddress]::TryParse($lanIp, [ref]$parsed)
    $isV4 = $isIp -and $parsed.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork
    $notLoopback = $lanIp -notlike "127.*" -and $lanIp -notlike "169.254.*"
    Write-Check "Get-JarvisLanIPv4" ($isV4 -and $notLoopback) $lanIp
}

# ------------------------------------------------------------------- 3. venv
$python = $null
try { $python = Test-JarvisVenv -Root $root } catch { Write-Check "Test-JarvisVenv" $false $_.Exception.Message }
Write-Check "Test-JarvisVenv" ([bool]($python -and (Test-Path -LiteralPath $python))) $python

# ------------------------------------------------------------------ 4. token
$token = Read-JarvisEnvValue -Name "JARVIS_API_TOKEN"
$tokenOk = $token -and $token.Length -ge 32 -and $token -notmatch '^(replace_|your_.*_here|changeme|change_me|placeholder)'
$tokenDetail = if ($token) { "present, $($token.Length) chars" } else { "missing or placeholder in .env" }
Write-Check "Read-JarvisEnvValue (JARVIS_API_TOKEN)" ([bool]$tokenOk) $tokenDetail

# ----------------------------------------------------------------- 5. cert
if ($lanIp -and $python) {
    $certInfo = $null
    try { $certInfo = New-JarvisHttpsCert -LanIp $lanIp } catch {
        Write-Check "New-JarvisHttpsCert" $false $_.Exception.Message
    }
    if ($certInfo) {
        $filesOk = (Test-Path -LiteralPath $certInfo.Cert) -and (Test-Path -LiteralPath $certInfo.Key) -and
            (Test-Path -LiteralPath $certInfo.CaCopy)
        Write-Check "New-JarvisHttpsCert (files)" $filesOk "cert.pem, key.pem, jarvis-ca.crt under data\tls"

        $verifier = Join-Path $root "scripts\verify_tls.py"
        if (Test-Path -LiteralPath $verifier) {
            $verifyArgs = @($verifier, "--mode", "local", "--host", $lanIp, "--cert", $certInfo.Cert)
            $verifyOutput = Invoke-NativeMerged { & $python @verifyArgs 2>&1 } | Out-String
            $verifyOk = ($LASTEXITCODE -eq 0)
            if (-not $verifyOk) { Write-Host $verifyOutput.Trim() -ForegroundColor DarkGray }
            Write-Check "verify_tls.py --mode local" $verifyOk "CA + validity + SAN covers $lanIp"
        } else {
            Write-Check "verify_tls.py --mode local" $false "missing $verifier"
        }
    }
} else {
    Write-Check "New-JarvisHttpsCert" $false "skipped (no LAN IP or venv)"
}

# ------------------------------------------------------------------ 6. URL
if ($lanIp) {
    $url = Get-JarvisMobileUrl -LanIp $lanIp
    $urlOk = $url -eq "https://${lanIp}:8443"
    Write-Check "Get-JarvisMobileUrl" $urlOk $url
}

# ----------------------------------------------------------- 7. health probe
# A dead endpoint must return $false (not throw); an already-running backend
# may return $true - both are correct, so only the contract is asserted.
$healthOk = $false
$healthDetail = ""
try {
    $dead = Test-JarvisBackendHealth -Url "https://127.0.0.1:1" -TimeoutSeconds 2
    if ($dead -isnot [bool]) {
        $healthDetail = "expected [bool] for a dead endpoint, got $($dead.GetType().Name)"
    } elseif ($dead) {
        $healthDetail = "dead endpoint unexpectedly reported healthy"
    } else {
        $healthOk = $true
        $healthDetail = "dead endpoint -> `$false"
        if ($lanIp) {
            $live = Test-JarvisBackendHealth -Url (Get-JarvisMobileUrl -LanIp $lanIp)
            $healthDetail += "; live backend on 8443 -> `$$live"
        }
    }
} catch {
    $healthDetail = "threw: $($_.Exception.Message)"
}
Write-Check "Test-JarvisBackendHealth" $healthOk $healthDetail

# ----------------------------------------------------------------- summary
Write-Host ""
if ($script:Failures -eq 0) {
    Write-Host "All mobile-common helpers passed." -ForegroundColor Green
    exit 0
}
Write-Host "$($script:Failures) check(s) failed." -ForegroundColor Red
exit 1
