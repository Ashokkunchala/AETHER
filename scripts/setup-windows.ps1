#Requires -Version 5.1
[CmdletBinding()]
param(
    [switch]$SkipDependencies,
    [switch]$SkipVerify,
    [switch]$NoApiKeyPrompt
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "AETHER Personal AI - Windows setup" -ForegroundColor Cyan
Write-Host "===================================" -ForegroundColor Cyan

$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $RepoRoot "app\main_enhanced.py"))) {
    throw "Run this script from the AETHER repository (scripts\setup-windows.ps1 must live in scripts\)."
}
Push-Location $RepoRoot
trap { Pop-Location; throw }

function Test-Placeholder([string]$Value) {
    if ([string]::IsNullOrWhiteSpace($Value)) { return $true }
    return ($Value.Trim() -match '^(replace_|your_.*_here|changeme|change_me|placeholder)')
}

function Set-EnvValue([string]$Text, [string]$Name, [string]$Value) {
    $escaped = [regex]::Escape($Name)
    $line = "$Name=$Value"
    if ($Text -match "(?m)^\s*$escaped=") {
        return [regex]::Replace($Text, "(?m)^\s*$escaped=.*$", [System.Text.RegularExpressions.MatchEvaluator]{ param($m) $line })
    }
    return $Text.TrimEnd() + [Environment]::NewLine + $line + [Environment]::NewLine
}

function New-Secret {
    $bytes = New-Object byte[] 48
    $rng = New-Object System.Security.Cryptography.RNGCryptoServiceProvider
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    return [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
}

# Return only an executable that actually runs Python 3.11+ (project minimum).
function Test-PythonRuntime {
    param([string]$Executable, [string[]]$LauncherArgs = @())
    try {
        $probeOutput = @(& $Executable @LauncherArgs -c "import sys; sys.exit(1) if sys.version_info < (3, 11) else print(sys.executable)" 2>$null)
        $probeExitCode = $LASTEXITCODE
        $candidate = $probeOutput | Select-Object -First 1
        if ($probeExitCode -eq 0 -and $candidate -and (Test-Path -LiteralPath $candidate.Trim() -PathType Leaf)) {
            return $candidate.Trim()
        }
    } catch {
        # Missing runtimes, Store aliases and launcher errors are failed probes.
    }
    return $null
}

function Find-PythonRuntime {
    $pyCommand = Get-Command py -CommandType Application -ErrorAction SilentlyContinue
    if ($pyCommand) {
        # A launcher's default can be old even when a supported runtime exists.
        # Prefer validated stable Python versions before an unqualified launcher default.
        foreach ($selector in @("-3.14", "-3.13", "-3.12", "-3.11")) {
            $candidate = Test-PythonRuntime -Executable $pyCommand.Source -LauncherArgs @($selector)
            if ($candidate) { return $candidate }
        }
    }
    foreach ($name in @("python", "python3")) {
        foreach ($command in @(Get-Command $name -CommandType Application -All -ErrorAction SilentlyContinue)) {
            $candidate = Test-PythonRuntime -Executable $command.Source
            if ($candidate) { return $candidate }
        }
    }
    # Some existing per-user installs have neither a launcher nor PATH entries.
    foreach ($version in @("314", "313", "312", "311")) {
        $path = Join-Path $env:LOCALAPPDATA "Programs\Python\Python$version\python.exe"
        if (Test-Path -LiteralPath $path -PathType Leaf) {
            $candidate = Test-PythonRuntime -Executable $path
            if ($candidate) { return $candidate }
        }
    }
    return $null
}

function Update-SessionPath {
    $paths = @(
        [Environment]::GetEnvironmentVariable("Path", "Machine"),
        [Environment]::GetEnvironmentVariable("Path", "User"),
        $env:Path
    )
    $env:Path = ($paths | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }) -join ";"
}

# ---------------------------------------------------------------- prerequisites
$pythonExe = Find-PythonRuntime
if (-not $pythonExe) {
    Update-SessionPath
    $pythonExe = Find-PythonRuntime
}
if (-not $pythonExe) {
    throw "Python 3.11+ is required. Install it from https://www.python.org/downloads/windows/ (enable Add python.exe to PATH), reopen PowerShell, and rerun this script."
}
Write-Host "Using Python: $pythonExe" -ForegroundColor Green

$venvPath = Join-Path $RepoRoot ".venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"

if (-not $SkipDependencies) {
    if (-not (Test-Path $venvPython)) {
        Write-Host "Creating virtual environment..."
        & $pythonExe -m venv $venvPath
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path $venvPython)) { throw "Could not create .venv." }
    }

    Write-Host "Installing dependencies..."
    & $venvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed." }
    & $venvPython -m pip install -r (Join-Path $RepoRoot "requirements-dev.txt")
    if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }

    # Install the desktop voice stack as part of the standard Windows setup.
    # Keep it separate from requirements-dev.txt so Linux CI remains audio-free.
    $voiceRequirements = Join-Path $RepoRoot "requirements-voice.txt"
    if (-not (Test-Path -LiteralPath $voiceRequirements)) {
        throw "Required voice dependency file is missing: $voiceRequirements"
    }
    Write-Host "Installing desktop voice and wake-word dependencies..."
    & $venvPython -m pip install -r $voiceRequirements
    if ($LASTEXITCODE -ne 0) { throw "Voice dependency installation failed." }

    & $venvPython -c "import sounddevice, webrtcvad, openwakeword, scipy"
    if ($LASTEXITCODE -ne 0) { throw "Voice dependency verification failed; inspect the pip output above." }
} else {
    if (-not (Test-Path $venvPython)) { throw "-SkipDependencies was set but .venv is missing. Run without -SkipDependencies first." }
    Write-Warning "Dependency installation skipped by -SkipDependencies."
}

# ------------------------------------------------------------------- .env setup
$envPath = Join-Path $RepoRoot ".env"
$examplePath = Join-Path $RepoRoot ".env.example"
if (-not (Test-Path $envPath)) {
    if (-not (Test-Path $examplePath)) { throw ".env.example is missing; cannot create a safe environment file." }
    Copy-Item $examplePath $envPath
    Write-Host "Created .env from .env.example." -ForegroundColor Yellow
}

$text = Get-Content -Raw -Path $envPath
$dirty = $false

foreach ($name in @("AETHER_API_TOKEN", "SECRET_KEY", "AETHER_AGENT_TOKEN")) {
    $match = [regex]::Match($text, "(?m)^\s*$([regex]::Escape($name))=(.*)$")
    if (-not $match.Success -or (Test-Placeholder $match.Groups[1].Value) -or $match.Groups[1].Value.Trim().Length -lt 32) {
        $text = Set-EnvValue $text $name (New-Secret)
        $dirty = $true
        Write-Host "Generated $name (value hidden)." -ForegroundColor Green
    }
}

# Keep the local server bound to loopback by default.
if ($text -notmatch '(?m)^\s*HOST=') {
    $text = Set-EnvValue $text "HOST" "127.0.0.1"
    $dirty = $true
} elseif ($text -match '(?m)^\s*HOST=(.*)$' -and $Matches[1].Trim() -ne "127.0.0.1") {
    Write-Warning "HOST is not 127.0.0.1. Keep this prototype local; do not expose it publicly."
}

$providerNames = @("GEMINI_API_KEY", "OPENROUTER_API_KEY", "GROQ_API_KEY")
$hasProvider = $false
foreach ($name in $providerNames) {
    $m = [regex]::Match($text, "(?m)^\s*$([regex]::Escape($name))=(.*)$")
    if ($m.Success -and -not (Test-Placeholder $m.Groups[1].Value)) { $hasProvider = $true }
}

if (-not $hasProvider -and -not $NoApiKeyPrompt) {
    Write-Host "No AI provider API key is configured. A key is required for real AI responses." -ForegroundColor Yellow
    $secureKey = Read-Host "Gemini API key (press Enter to configure it later)" -AsSecureString
    if ($secureKey.Length -gt 0) {
        $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
        try { $apiKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
        finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr); $secureKey.Dispose() }
        if (Test-Placeholder $apiKey) { throw "The entered key looks like a placeholder. No API key was saved." }
        $text = Set-EnvValue $text "GEMINI_API_KEY" $apiKey
        $apiKey = $null
        $hasProvider = $true
        $dirty = $true
        Write-Host "Gemini key saved locally (value hidden)." -ForegroundColor Green
    } else {
        $secureKey.Dispose()
        Write-Warning "No provider key entered. Tests still run, but real AI chat and Live Voice need a valid key in .env."
    }
} elseif ($hasProvider) {
    Write-Host "At least one AI provider key appears configured (not tested against the provider)." -ForegroundColor Green
} else {
    Write-Warning "API-key prompt skipped by -NoApiKeyPrompt. Real AI requests need a valid provider key."
}

if ($dirty) {
    # UTF-8 without BOM for Windows PowerShell 5.1 compatibility.
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($envPath, $text, $utf8NoBom)
    Write-Host ".env saved; secret values were not printed." -ForegroundColor Green
}

# -------------------------------------------------------------------- verify
if (-not $SkipVerify) {
    Write-Host ""
    Write-Host "Running verification (aether doctor)..." -ForegroundColor Cyan
    & $venvPython (Join-Path $RepoRoot "aether_cli.py") doctor
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "aether doctor reported critical failures. Fix the FAIL rows above, then rerun: .\.venv\Scripts\python.exe aether_cli.py doctor"
    } else {
        Write-Host "Verification passed." -ForegroundColor Green
    }
}

Pop-Location

Write-Host ""
Write-Host "Setup complete. Start the app with:" -ForegroundColor Green
Write-Host "  .\scripts\start-windows.ps1"
Write-Host ""
Write-Host "Then open http://127.0.0.1:8000"
Write-Host "Keep the host as 127.0.0.1. Do not expose this starter publicly without authentication and a security review."
