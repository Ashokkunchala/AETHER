#Requires -Version 5.1
<#
.SYNOPSIS
    Uninstall JARVIS Personal AI from this Windows user account.

.DESCRIPTION
    Removes, in order:
      1. The "JARVIS Personal AI" sign-in scheduled task (created by INSTALL-JARVIS.ps1).
      2. The per-user Startup shortcut JARVIS.lnk (created by scripts/install-jarvis-startup.ps1).
      3. The install directory %LOCALAPPDATA%\Programs\JarvisPersonalAI, when -RemoveFiles
         is passed (a copy of .env is preserved next to the removal as .env.removed-<timestamp>
         unless -PurgeData is also passed).

    It never touches the source checkout you may have cloned yourself, never runs as
    administrator, and never deletes anything outside the paths listed above.

.PARAMETER RemoveFiles
    Also delete the install directory. Without it, only auto-start entries are removed.

.PARAMETER PurgeData
    With -RemoveFiles, delete .env and the data/ folder too instead of preserving .env.

.PARAMETER InstallRoot
    Override the install directory. Defaults to %LOCALAPPDATA%\Programs\JarvisPersonalAI.

.EXAMPLE
    .\scripts\uninstall-jarvis.ps1
    # Removes auto-start only.

.EXAMPLE
    .\scripts\uninstall-jarvis.ps1 -RemoveFiles
    # Removes auto-start and the installed files (keeps a copy of .env).

.EXAMPLE
    .\scripts\uninstall-jarvis.ps1 -RemoveFiles -PurgeData
    # Full removal including .env and data/.
#>
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'High')]
param(
    [switch]$RemoveFiles,
    [switch]$PurgeData,
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA "Programs\JarvisPersonalAI")
)

$ErrorActionPreference = "Stop"

$taskName = "JARVIS Personal AI"
$shortcutName = "JARVIS.lnk"
$removedAny = $false

Write-Host ""
Write-Host "JARVIS Personal AI - uninstall" -ForegroundColor Cyan

# 1. Sign-in scheduled task ----------------------------------------------------
$task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($task) {
    if ($PSCmdlet.ShouldProcess($taskName, "Unregister scheduled task")) {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
        Write-Host "Removed scheduled task: $taskName" -ForegroundColor Green
        $removedAny = $true
    }
} else {
    Write-Host "No scheduled task named '$taskName' found." -ForegroundColor DarkGray
}

# 2. Startup shortcut -----------------------------------------------------------
$startupFolder = [Environment]::GetFolderPath("Startup")
$linkPath = Join-Path $startupFolder $shortcutName
if ($startupFolder -and (Test-Path -LiteralPath $linkPath)) {
    if ($PSCmdlet.ShouldProcess($linkPath, "Remove startup shortcut")) {
        Remove-Item -LiteralPath $linkPath -Force
        Write-Host "Removed startup shortcut: $linkPath" -ForegroundColor Green
        $removedAny = $true
    }
} else {
    Write-Host "No startup shortcut at $linkPath found." -ForegroundColor DarkGray
}

# 3. Installed files ------------------------------------------------------------
if (-not $RemoveFiles) {
    Write-Host "Installed files left in place at: $InstallRoot (pass -RemoveFiles to delete)." -ForegroundColor Yellow
} elseif (-not (Test-Path -LiteralPath $InstallRoot)) {
    Write-Host "Install directory not found: $InstallRoot" -ForegroundColor DarkGray
} else {
    if ($PurgeData) {
        $warning = "Delete the entire install directory including .env and data/?"
    } else {
        $warning = "Delete the install directory (a copy of .env will be preserved)?"
    }
    if ($PSCmdlet.ShouldProcess($InstallRoot, $warning)) {
        if (-not $PurgeData) {
            $envFile = Join-Path $InstallRoot ".env"
            if (Test-Path -LiteralPath $envFile) {
                $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
                $backupPath = Join-Path (Split-Path -Parent $InstallRoot) ".env.removed-$stamp"
                Copy-Item -LiteralPath $envFile -Destination $backupPath -Force
                Write-Host "Preserved credentials at: $backupPath" -ForegroundColor Yellow
            }
        }

        # Stop a running backend started from this install before deleting files.
        $port = 8000
        $envFile = Join-Path $InstallRoot ".env"
        if (Test-Path -LiteralPath $envFile) {
            $portLine = Get-Content -LiteralPath $envFile | Where-Object { $_ -match '^\s*PORT=' } | Select-Object -Last 1
            if ($portLine -and $portLine -match '^\s*PORT=(\d+)') { $port = [int]$Matches[1] }
        }
        $listeners = @(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
        foreach ($listener in $listeners) {
            $proc = Get-Process -Id $listener.OwningProcess -ErrorAction SilentlyContinue
            if ($proc -and $proc.ProcessName -match 'python|uvicorn') {
                if ($PSCmdlet.ShouldProcess("$($proc.ProcessName) (PID $($proc.Id))", "Stop process listening on port $port")) {
                    Stop-Process -Id $proc.Id -Force
                    Write-Host "Stopped $($proc.ProcessName) on port $port." -ForegroundColor Green
                }
            }
        }

        Remove-Item -LiteralPath $InstallRoot -Recurse -Force
        Write-Host "Removed install directory: $InstallRoot" -ForegroundColor Green
        $removedAny = $true
    }
}

Write-Host ""
if ($WhatIfPreference) {
    Write-Host "WhatIf complete: no changes were made (dry run)." -ForegroundColor Yellow
} elseif ($removedAny) {
    Write-Host "Uninstall complete." -ForegroundColor Green
} else {
    Write-Host "Nothing to remove." -ForegroundColor Yellow
}
Write-Host "Your cloned source checkout and global Python packages were not touched." -ForegroundColor DarkGray
