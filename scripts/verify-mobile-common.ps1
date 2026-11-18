#Requires -Version 5.1
<#
.SYNOPSIS
    Verify the shared mobile helpers in scripts\mobile-common.ps1.

.DESCRIPTION
    Exercises every helper that scripts\setup-mobile.ps1 and
    scripts\start-mobile.ps1 depend on, without starting a server:

      1. Get-AETHERRepoRoot      - resolves the repository root
      2. Get-AETHERLanIPv4       - returns a real (non-loopback) LAN address
      3. Test-AETHERVenv         - .venv\Scripts\python.exe exists
      4. Read-AETHEREnvValue     - AETHER_API_TOKEN present, 32+ chars, not a placeholder
      5. New-AETHERHttpsCert     - data\tls certificate files exist and pass
                                   scripts\verify_tls.py --mode local (CA:TRUE,
                                   >= 7 days validity, SAN covers the LAN IP)
      6. Get-AETHERMobileUrl     - https://<lan-ip>:8443
      7. Test-AETHERBackendHealth - returns a boolean for both a dead endpoint
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
Write-Host "AETHER mobile-common.ps1 helper verification" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan

# --------------------------------------------------------------- 1. repo root
$root = Get-AETHERRepoRoot
$rootOk = $root -and (Test-Path -LiteralPath (Join-Path $root "app\main_enhanced.py")) -and
    (Test-Path -LiteralPath (Join-Path $root "scripts\mobile-common.ps1"))
Write-Check "Get-AETHERRepoRoot" ([bool]$rootOk) $root

# ----------------------------------------------------------------- 2. LAN IP
$lanIp = $null
try { $lanIp = Get-AETHERLanIPv4 } catch { Write-Check "Get-AETHERLanIPv4" $false $_.Exception.Message }
if ($lanIp) {
    $parsed = $null
    $isIp = [System.Net.IPAddress]::TryParse($lanIp, [ref]$parsed)
    $isV4 = $isIp -and $parsed.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork
    $notLoopback = $lanIp -notlike "127.*" -and $lanIp -notlike "169.254.*"
    Write-Check "Get-AETHERLanIPv4" ($isV4 -and $notLoopback) $lanIp
}

# ------------------------------------------------------------------- 3. venv
$python = $null
try { $python = Test-AETHERVenv -Root $root } catch { Write-Check "Test-AETHERVenv" $false $_.Exception.Message }
Write-Check "Test-AETHERVenv" ([bool]($python -and (Test-Path -LiteralPath $python))) $python

# ------------------------------------------------------------------ 4. token
$token = Read-AETHEREnvValue -Name "AETHER_API_TOKEN"
$tokenOk = $token -and $token.Length -ge 32 -and $token -notmatch '^(replace_|your_.*_here|changeme|change_me|placeholder)'
$tokenDetail = if ($token) { "present, $($token.Length) chars" } else { "missing or placeholder in .env" }
Write-Check "Read-AETHEREnvValue (AETHER_API_TOKEN)" ([bool]$tokenOk) $tokenDetail

# ----------------------------------------------------------------- 5. cert
if ($lanIp -and $python) {
    $certInfo = $null
    try { $certInfo = New-AETHERHttpsCert -LanIp $lanIp } catch {
        Write-Check "New-AETHERHttpsCert" $false $_.Exception.Message
    }
    if ($certInfo) {
        $filesOk = (Test-Path -LiteralPath $certInfo.Cert) -and (Test-Path -LiteralPath $certInfo.Key) -and
            (Test-Path -LiteralPath $certInfo.CaCopy)
        Write-Check "New-AETHERHttpsCert (files)" $filesOk "cert.pem, key.pem, aether-ca.crt under data\tls"

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
    Write-Check "New-AETHERHttpsCert" $false "skipped (no LAN IP or venv)"
}

# ------------------------------------------------------------------ 6. URL
if ($lanIp) {
    $url = Get-AETHERMobileUrl -LanIp $lanIp
    $urlOk = $url -eq "https://${lanIp}:8443"
    Write-Check "Get-AETHERMobileUrl" $urlOk $url
}

# ----------------------------------------------------------- 7. health probe
# A dead endpoint must return $false (not throw); an already-running backend
# may return $true - both are correct, so only the contract is asserted.
$healthOk = $false
$healthDetail = ""
try {
    $dead = Test-AETHERBackendHealth -Url "https://127.0.0.1:1" -TimeoutSeconds 2
    if ($dead -isnot [bool]) {
        $healthDetail = "expected [bool] for a dead endpoint, got $($dead.GetType().Name)"
    } elseif ($dead) {
        $healthDetail = "dead endpoint unexpectedly reported healthy"
    } else {
        $healthOk = $true
        $healthDetail = "dead endpoint -> `$false"
        if ($lanIp) {
            $live = Test-AETHERBackendHealth -Url (Get-AETHERMobileUrl -LanIp $lanIp)
            $healthDetail += "; live backend on 8443 -> `$$live"
        }
    }
} catch {
    $healthDetail = "threw: $($_.Exception.Message)"
}
Write-Check "Test-AETHERBackendHealth" $healthOk $healthDetail

# ----------------------------------------------------------------- summary
Write-Host ""
if ($script:Failures -eq 0) {
    Write-Host "All mobile-common helpers passed." -ForegroundColor Green
    exit 0
}
Write-Host "$($script:Failures) check(s) failed." -ForegroundColor Red
exit 1
