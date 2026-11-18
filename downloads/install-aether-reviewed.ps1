#Requires -Version 5.1
<# Owner-reviewed fresh-folder installer, pinned by CI. No startup registration,
existing installation overwrite, environment secret entry, firewall or device action. #>
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$commit = 'e56382825f82c79f916d63fb83e9ee3771ef71c5'
if ($commit -notmatch '^[0-9a-f]{40}$') { throw 'This payload must be stamped with the verified CI commit before distribution.' }
Write-Host 'AETHER - reviewed Windows setup' -ForegroundColor Cyan
Write-Host "Source commit: $commit"
Write-Host 'Requires Windows 10/11 and a working Python 3.11+ installation.'
Write-Host 'This downloads that source commit and installs Python packages only after your review.'
Write-Host 'No existing install is overwritten. No sign-in task, backend listener, phone pairing or app launch is started.'
Write-Host 'No API key is requested by this launcher. Provider use is a separate reviewed step.'
if ((Read-Host 'Type DOWNLOAD AETHER to continue') -cne 'DOWNLOAD AETHER') { Write-Host 'Cancelled. Nothing downloaded.'; exit 0 }
$parent = Join-Path $env:LOCALAPPDATA 'Programs'
$destination = Join-Path $parent ('AETHER-' + $commit.Substring(0, 12) + '-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
if (Test-Path -LiteralPath $destination) { throw 'Destination already exists. No overwrite allowed.' }
$tempRoot = Join-Path $env:TEMP ('aether-download-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tempRoot | Out-Null
try {
    $archive = Join-Path $tempRoot 'source.zip'
    $expanded = Join-Path $tempRoot 'source'
    $uri = "https://github.com/Ashokkunchala/AETHER/archive/$commit.zip"
    Invoke-WebRequest -UseBasicParsing -Uri $uri -OutFile $archive
    Expand-Archive -LiteralPath $archive -DestinationPath $expanded
    $roots = @(Get-ChildItem -LiteralPath $expanded -Directory)
    if ($roots.Count -ne 1 -or $roots[0].Name -cne ('AETHER-' + $commit)) { throw 'Unexpected source archive layout. Nothing installed.' }
    if (-not (Test-Path -LiteralPath (Join-Path $roots[0].FullName 'scripts\setup-windows.ps1') -PathType Leaf)) { throw 'Reviewed setup script missing.' }
    if (-not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent | Out-Null }
    Move-Item -LiteralPath $roots[0].FullName -Destination $destination
    Set-Content -LiteralPath (Join-Path $destination 'AETHER-SOURCE-COMMIT.txt') -Value $commit -Encoding ASCII
    Write-Host "Downloaded source to: $destination" -ForegroundColor Green
    Write-Host 'Review scripts\setup-windows.ps1 before continuing. Package installation uses network/package indexes and executes package build steps.'
    Write-Host 'It creates a new local .venv and .env with random backend secrets. No sign-in task is installed by this path.'
    if ((Read-Host 'Type INSTALL REVIEWED PACKAGES to install into this new folder') -cne 'INSTALL REVIEWED PACKAGES') {
        Write-Host 'Source retained. No Python packages installed. See docs\INSTALLABLE-FILES.md in that folder.'
        exit 0
    }
    Push-Location $destination
    try {
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $destination 'scripts\setup-windows.ps1') -NoApiKeyPrompt
        if ($LASTEXITCODE -ne 0) { throw 'Setup failed. Source retained; do not start AETHER until the error is checked.' }
    } finally { Pop-Location }
    Write-Host 'AETHER source/package setup finished. No provider or device acceptance claim.' -ForegroundColor Green
    Write-Host "Open $destination\docs\OWNER-DEVICE-AND-CLOUD-SETUP.md for the reviewed local checks."
    Write-Host 'Do not enable startup, firewall changes, a public tunnel or device effects from an old guide.'
} finally {
    # Clean only the unique temporary download directory created by this process.
    if (Test-Path -LiteralPath $tempRoot) { Remove-Item -LiteralPath $tempRoot -Recurse -Force }
}
