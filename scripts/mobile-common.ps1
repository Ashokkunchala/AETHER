#Requires -Version 5.1
<#
.SYNOPSIS
    Shared helpers for the JARVIS mobile (phone) setup scripts.

.DESCRIPTION
    Dot-source this file from scripts\setup-mobile.ps1 and scripts\start-mobile.ps1:

        . (Join-Path $PSScriptRoot "mobile-common.ps1")

    It provides LAN IP detection, self-signed HTTPS certificate generation,
    .env token reading and backend health checks. Nothing here starts a
    server or modifies files except when New-JarvisHttpsCert writes the
    certificate into data\tls.
#>

Set-StrictMode -Version Latest

# Captured while this file is being dot-sourced: functions must not rely on
# $PSScriptRoot at call time because it would resolve to the caller's script.
$script:MobileHttpsPort = 8443
$script:MobileRepoRoot = Split-Path -Parent $PSScriptRoot

function Get-JarvisRepoRoot {
    # mobile-common.ps1 lives in <repo>\scripts
    return $script:MobileRepoRoot
}

function Get-JarvisLanIPv4 {
    <#
    .SYNOPSIS
        Return the preferred LAN IPv4 address of this machine.
    .DESCRIPTION
        Picks the address of the interface owning the default IPv4 route
        (the one actually used to reach the phone's network), skipping
        loopback and APIPA (169.254.x.x) fallbacks. Falls back to a
        best-effort scan when no default route exists (offline machines).
    #>
    $candidates = @()

    try {
        $route = Get-NetRoute -AddressFamily IPv4 -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue |
            Sort-Object -Property RouteMetric |
            Select-Object -First 1
        if ($route) {
            $addr = Get-NetIPAddress -AddressFamily IPv4 -InterfaceIndex $route.InterfaceIndex -ErrorAction SilentlyContinue |
                Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } |
                Select-Object -First 1
            if ($addr) { $candidates += $addr.IPAddress }
        }
    } catch { }

    if (-not $candidates) {
        try {
            $candidates = @(
                [System.Net.Dns]::GetHostAddresses([System.Net.Dns]::GetHostName()) |
                    Where-Object { $_.AddressFamily -eq 'InterNetwork' } |
                    ForEach-Object { $_.IPAddressToString } |
                    Where-Object { $_ -notlike '127.*' -and $_ -notlike '169.254.*' }
            )
        } catch { }
    }

    if (-not $candidates) {
        throw "No LAN IPv4 address found. Connect this machine to the same network as your phone and rerun."
    }
    return $candidates[0]
}

function Read-JarvisEnvValue {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [string]$EnvPath = (Join-Path (Get-JarvisRepoRoot) ".env")
    )
    if (-not (Test-Path -LiteralPath $EnvPath)) { return $null }
    $line = Get-Content -LiteralPath $EnvPath |
        Where-Object { $_ -match "^\s*$([regex]::Escape($Name))\s*=" } |
        Select-Object -Last 1
    if (-not $line) { return $null }
    $value = ($line -replace "^\s*$([regex]::Escape($Name))\s*=\s*", "").Trim().Trim('"').Trim("'")
    if ([string]::IsNullOrWhiteSpace($value)) { return $null }
    if ($value -match '^(replace_|your_.*_here|changeme|change_me|placeholder)') { return $null }
    return $value
}

function Test-JarvisVenv {
    param([string]$Root = (Get-JarvisRepoRoot))
    $python = Join-Path $Root ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $python)) {
        throw "Virtual environment missing at $python. Run INSTALL_JARVIS.bat or scripts\setup-windows.ps1 first."
    }
    return $python
}

function Invoke-NativeMerged {
    <#
    .SYNOPSIS
        Run a native command with 2>&1 redirection under $ErrorActionPreference = 'Stop'.
    .DESCRIPTION
        PS 5.1 turns native stderr into a terminating NativeCommandError when
        EAP is Stop; toggling to Continue for the call lets stderr flow as
        plain output. Use for python/uvicorn/adb invocations that write to stderr.
    #>
    param([scriptblock]$Block)
    $eap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try { & $Block } finally { $ErrorActionPreference = $eap }
}

function New-JarvisHttpsCert {
    <#
    .SYNOPSIS
        Ensure data\tls holds a valid self-signed certificate covering this machine's LAN IP.
    .OUTPUTS
        Hashtable with Cert, Key, CaCopy (absolute paths) and LanIp.
    #>
    param(
        [Parameter(Mandatory = $true)][string]$LanIp,
        [switch]$Force
    )
    $root = Get-JarvisRepoRoot
    $python = Test-JarvisVenv -Root $root
    $outDir = Join-Path $root "data\tls"
    $generator = Join-Path $root "scripts\generate_https_cert.py"
    if (-not (Test-Path -LiteralPath $generator)) {
        throw "Missing $generator."
    }

    # NOTE: never name this $args - inside the Invoke-NativeMerged scriptblock
    # $args is the (empty) automatic variable of that scriptblock, and the splat
    # would silently pass no arguments to Python.
    $genArgs = @($generator, "--out-dir", $outDir, "--ip", $LanIp, "--hostname", "localhost")
    $computerName = $env:COMPUTERNAME
    if ($computerName) { $genArgs += @("--hostname", $computerName) }
    if ($Force) { $genArgs += "--force" }

    Invoke-NativeMerged { & $python @genArgs 2>&1 } | ForEach-Object { Write-Host $_ }
    if ($LASTEXITCODE -ne 0) {
        throw "Certificate generation failed (exit $LASTEXITCODE)."
    }

    $cert = Join-Path $outDir "cert.pem"
    $key = Join-Path $outDir "key.pem"
    $caCopy = Join-Path $outDir "jarvis-ca.crt"
    foreach ($path in @($cert, $key)) {
        if (-not (Test-Path -LiteralPath $path)) { throw "Expected certificate file missing: $path" }
    }

    return @{ Cert = $cert; Key = $key; CaCopy = $caCopy; LanIp = $LanIp }
}

function Get-JarvisMobileUrl {
    param(
        [Parameter(Mandatory = $true)][string]$LanIp,
        [int]$Port = $script:MobileHttpsPort
    )
    return "https://${LanIp}:$Port"
}

function Initialize-JarvisCertBypass {
    <#
    .SYNOPSIS
        Install a certificate-validation callback that trusts our self-signed cert.
    .DESCRIPTION
        PS 5.1 (.NET Framework) invokes ServerCertificateValidationCallback on a
        network thread with no PowerShell runspace, so a scriptblock like
        { $true } throws "There is no Runspace available to run scripts in this
        thread" and aborts the request. Compile a static C# delegate instead.

        PS 6+ callers should use Invoke-WebRequest -SkipCertificateCheck and
        never touch the shared callback. Returns the previous callback (or
        $null) so the caller can restore it in a finally block.
    #>
    if ($PSVersionTable.PSVersion.Major -ge 6) { return $null }
    if (-not ('Jarvis.SelfSignedTrust' -as [type])) {
        Add-Type -TypeDefinition @"
using System.Net;
using System.Net.Security;
using System.Security.Cryptography.X509Certificates;

namespace Jarvis
{
    public static class SelfSignedTrust
    {
        public static bool Validate(
            object sender,
            X509Certificate certificate,
            X509Chain chain,
            SslPolicyErrors sslPolicyErrors)
        {
            return true;
        }
    }
}
"@
    }
    $previous = [System.Net.ServicePointManager]::ServerCertificateValidationCallback
    # PS cannot assign a PSMethod to a delegate-typed property; build the
    # RemoteCertificateValidationCallback explicitly from the MethodInfo.
    $method = [Jarvis.SelfSignedTrust].GetMethod('Validate')
    $delegate = [System.Delegate]::CreateDelegate(
        [System.Net.Security.RemoteCertificateValidationCallback], $method)
    [System.Net.ServicePointManager]::ServerCertificateValidationCallback = $delegate
    return $previous
}

function Restore-JarvisCertBypass {
    param($PreviousCallback)
    if ($PSVersionTable.PSVersion.Major -lt 6) {
        [System.Net.ServicePointManager]::ServerCertificateValidationCallback = $PreviousCallback
    }
}

function Test-JarvisBackendHealth {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [int]$TimeoutSeconds = 3
    )
    # Self-signed certificate: verification must be bypassed because we are
    # only probing our own machine's loopback/LAN endpoint.
    try {
        if (Get-Command Invoke-WebRequest -ErrorAction SilentlyContinue) {
            # PS 6+ has -SkipCertificateCheck; PS 5.1 needs the delegate above.
            $params = @{ Uri = "$Url/health"; TimeoutSec = $TimeoutSeconds; UseBasicParsing = $true }
            if ($PSVersionTable.PSVersion.Major -ge 6) { $params["SkipCertificateCheck"] = $true }
            $previous = Initialize-JarvisCertBypass
            try {
                $response = Invoke-WebRequest @params
                return ($response.StatusCode -eq 200)
            } finally {
                Restore-JarvisCertBypass -PreviousCallback $previous
            }
        }
    } catch { }
    return $false
}

function Wait-JarvisBackendHealth {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [int]$Attempts = 40
    )
    for ($i = 0; $i -lt $Attempts; $i++) {
        Start-Sleep -Milliseconds 750
        if (Test-JarvisBackendHealth -Url $Url) { return $true }
    }
    return $false
}

function Add-JarvisFirewallRule {
    <#
    .SYNOPSIS
        Best-effort inbound firewall allow rule for the HTTPS port (private LAN use).
    .DESCRIPTION
        Requires elevation to create; when it fails the caller prints the
        elevated command instead of failing the setup. The rule is scoped to
        the TCP port on private profiles only.
    #>
    param(
        [int]$Port = $script:MobileHttpsPort
    )
    $ruleName = "JARVIS Mobile HTTPS (TCP $Port)"
    $existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Host "[PASS] Firewall rule already present: $ruleName" -ForegroundColor Green
        return $true
    }
    try {
        New-NetFirewallRule -DisplayName $ruleName `
            -Direction Inbound -Protocol TCP -LocalPort $Port `
            -Action Allow -Profile Private -ErrorAction Stop | Out-Null
        Write-Host "[PASS] Firewall rule created: $ruleName (private profiles only)" -ForegroundColor Green
        return $true
    } catch {
        Write-Warning "Could not create the firewall rule (administrator rights needed)."
        Write-Host "  Run this once in an elevated PowerShell to let the phone connect:" -ForegroundColor Yellow
        Write-Host "  New-NetFirewallRule -DisplayName '$ruleName' -Direction Inbound -Protocol TCP -LocalPort $Port -Action Allow -Profile Private" -ForegroundColor Yellow
        return $false
    }
}
