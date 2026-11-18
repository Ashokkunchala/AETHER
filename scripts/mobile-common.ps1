#Requires -Version 5.1
<#
.SYNOPSIS
    Shared helpers for the AETHER mobile (phone) setup scripts.

.DESCRIPTION
    Dot-source this file from scripts\setup-mobile.ps1 and scripts\start-mobile.ps1:

        . (Join-Path $PSScriptRoot "mobile-common.ps1")

    It provides LAN IP detection, self-signed HTTPS certificate generation,
    .env token reading and backend health checks. Nothing here starts a
    server or modifies files except when New-AETHERHttpsCert writes the
    certificate into data\tls.
#>

Set-StrictMode -Version Latest

# Captured while this file is being dot-sourced: functions must not rely on
# $PSScriptRoot at call time because it would resolve to the caller's script.
$script:MobileHttpsPort = 8443
$script:MobileRepoRoot = Split-Path -Parent $PSScriptRoot

function Get-AETHERRepoRoot {
    # mobile-common.ps1 lives in <repo>\scripts
    return $script:MobileRepoRoot
}

function Get-AETHERLanIPv4 {
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

function Read-AETHEREnvValue {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [string]$EnvPath = (Join-Path (Get-AETHERRepoRoot) ".env")
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

function Test-AETHERVenv {
    param([string]$Root = (Get-AETHERRepoRoot))
    $python = Join-Path $Root ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $python)) {
        throw "Virtual environment missing at $python. Run INSTALL_AETHER.bat or scripts\setup-windows.ps1 first."
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

function New-AETHERHttpsCert {
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
    $root = Get-AETHERRepoRoot
    $python = Test-AETHERVenv -Root $root
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
    $caCopy = Join-Path $outDir "aether-ca.crt"
    foreach ($path in @($cert, $key)) {
        if (-not (Test-Path -LiteralPath $path)) { throw "Expected certificate file missing: $path" }
    }

    return @{ Cert = $cert; Key = $key; CaCopy = $caCopy; LanIp = $LanIp }
}

function Get-AETHERMobileUrl {
    param(
        [Parameter(Mandatory = $true)][string]$LanIp,
        [int]$Port = $script:MobileHttpsPort
    )
    return "https://${LanIp}:$Port"
}

function Test-AETHERBackendHealth {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [int]$TimeoutSeconds = 3
    )
    # This is a health-only probe to our own LAN endpoint. Use curl's
    # per-request --insecure option rather than installing a process-wide
    # certificate callback that would silently trust every HTTPS host.
    try {
        $curl = Get-Command curl.exe -CommandType Application -ErrorAction SilentlyContinue
        if (-not $curl) { return $false }
        $status = & $curl.Source --insecure --silent --show-error --max-time $TimeoutSeconds --output NUL --write-out "%{http_code}" "$Url/health" 2>$null
        return ($LASTEXITCODE -eq 0 -and "$status".Trim() -eq "200")
    } catch {
        return $false
    }
}

function Wait-AETHERBackendHealth {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [int]$Attempts = 40
    )
    for ($i = 0; $i -lt $Attempts; $i++) {
        Start-Sleep -Milliseconds 750
        if (Test-AETHERBackendHealth -Url $Url) { return $true }
    }
    return $false
}

function Add-AETHERFirewallRule {
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
    $ruleName = "AETHER Mobile HTTPS (TCP $Port)"
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
