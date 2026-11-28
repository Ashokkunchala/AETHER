#Requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('Install', 'Uninstall', 'Start', 'Stop', 'Restart', 'Status', 'Logs', 'Doctor')]
    [string]$Action = 'Install',

    [ValidateSet('hey_jarvis', 'hey_mycroft', 'alexa', 'hey_rhasspy')]
    [string]$WakeWord = 'hey_jarvis',

    [ValidateRange(0.02, 0.95)]
    [double]$Threshold = 0.5,

    [switch]$CallMode,
    [switch]$NoStart
)

$ErrorActionPreference = 'Stop'

$TaskName = 'AETHER Voice Service'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
$pythonw = Join-Path $root '.venv\Scripts\pythonw.exe'
$launcher = Join-Path $root 'scripts\aether_voice_service.py'
$cli = Join-Path $root 'aether_cli.py'
$envPath = Join-Path $root '.env'
$logDir = Join-Path $root 'data\logs'
$logFile = Join-Path $logDir 'voice-service.log'
$statusFile = Join-Path $logDir 'voice-service.json'
$principalName = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$invariant = [System.Globalization.CultureInfo]::InvariantCulture

function Assert-InstallPrereqs {
    foreach ($item in @($python, $pythonw, $launcher, $cli)) {
        if (-not (Test-Path -LiteralPath $item)) {
            throw "Missing required file: $item"
        }
    }
    if (-not (Test-Path -LiteralPath $envPath)) {
        throw "Missing $envPath. Run scripts\setup-windows.ps1 first."
    }

    $geminiKey = ''
    foreach ($line in [System.IO.File]::ReadAllLines($envPath)) {
        if ($line -match '^\s*GEMINI_API_KEY\s*=\s*(?<v>.*)$') {
            $geminiKey = $Matches['v'].Trim()
            break
        }
    }
    if ($geminiKey -notmatch '^(AIza[0-9A-Za-z_-]{35}|AQ\.[A-Za-z0-9_-]{20,200})$') {
        throw 'GEMINI_API_KEY in .env is empty, a placeholder, or malformed. Set a real Google AI Studio key (starts with AIza or AQ.) with Gemini Live access, then retry.'
    }

    & $python -c 'import sys; from aether.terminal.voice import missing_voice_packages; missing = missing_voice_packages(); sys.exit(1 if missing else 0)'
    if ($LASTEXITCODE -ne 0) {
        throw 'Voice packages are missing. Install with: .venv\Scripts\python.exe -m pip install -r requirements-voice.txt'
    }
}

function Set-EnvEntry {
    param(
        [Parameter(Mandatory = $true)][string]$Key,
        [Parameter(Mandatory = $true)][string]$Value
    )

    $lines = [System.IO.File]::ReadAllLines($envPath)
    $pattern = '^\s*' + [regex]::Escape($Key) + '\s*='
    $replaced = $false
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match $pattern) {
            $lines[$i] = "$Key=$Value"
            $replaced = $true
        }
    }
    if (-not $replaced) {
        if ($lines.Count -gt 0 -and -not [string]::IsNullOrWhiteSpace($lines[$lines.Count - 1])) {
            $lines += ''
        }
        $lines += '# AETHER always-on voice service'
        $lines += "$Key=$Value"
    }
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllLines($envPath, $lines, $utf8NoBom)
}

function Get-AetherTask {
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($null -eq $task) {
        throw "AETHER voice service is not installed. Run: .\scripts\install-aether-voice-service.ps1 -Action Install"
    }
    return $task
}

function Get-VoiceServiceProcesses {
    # Stop-ScheduledTask does not always reap the spawned pythonw.exe process.
    # Match on the exact launcher path so no unrelated Python process is touched.
    Get-CimInstance Win32_Process -Filter "Name = 'pythonw.exe' OR Name = 'python.exe'" |
        Where-Object { $_.CommandLine -and $_.CommandLine.Contains($launcher) }
}

function Stop-VoiceServiceProcesses {
    foreach ($proc in Get-VoiceServiceProcesses) {
        Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
    }
}

function Install-VoiceService {
    # Re-installing must not leave the previous instance holding the mic.
    if ($null -ne (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue)) {
        Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    }
    Stop-VoiceServiceProcesses
    Assert-InstallPrereqs

    $thresholdText = $Threshold.ToString($invariant)
    $enabledText = if ($CallMode) { 'false' } else { 'true' }
    Set-EnvEntry 'AETHER_WAKEWORD_MODEL' $WakeWord
    Set-EnvEntry 'AETHER_WAKEWORD_THRESHOLD' $thresholdText
    Set-EnvEntry 'AETHER_WAKEWORD_ENABLED' $enabledText

    Write-Host 'Preparing openWakeWord models (one-time download)...' -ForegroundColor Cyan
    & $python -c 'import openwakeword.utils as u; u.download_models()'
    if ($LASTEXITCODE -ne 0) {
        throw 'Could not download openWakeWord models. Check internet access and retry.'
    }

    $check = "from openwakeword.model import Model; m = Model(); keys = [k for k in m.models if '$WakeWord' in k]; print('MODEL_KEYS=' + ','.join(keys)); raise SystemExit(0 if keys else 2)"
    & $python -c $check
    if ($LASTEXITCODE -ne 0) {
        throw "Wake model '$WakeWord' is not available after download."
    }

    New-Item -ItemType Directory -Force -Path $logDir | Out-Null

    $argString = '"' + $launcher + '" --wake-word ' + $WakeWord +
        ' --threshold ' + $thresholdText +
        ' --wakeword-models-dir "' + (Join-Path $root 'aether\models\wakeword') + '"'
    if ($CallMode) {
        $argString += ' --call-mode'
    }

    $action = New-ScheduledTaskAction -Execute $pythonw -Argument $argString -WorkingDirectory $root
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $principalName
    $principal = New-ScheduledTaskPrincipal -UserId $principalName -LogonType Interactive -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -Hidden `
        -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
        -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
        -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew

    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
        -Principal $principal -Settings $settings `
        -Description 'Always-on AETHER voice assistant (wake word -> Gemini Live -> local tools)' -Force | Out-Null

    Write-Host "Installed scheduled task: $TaskName" -ForegroundColor Green
    Write-Host "Wake phrase: '$WakeWord' (threshold $thresholdText)" -ForegroundColor Cyan
    if ($CallMode) {
        Write-Host 'Call mode: the microphone streams immediately; no wake word is used.' -ForegroundColor Yellow
    }
    Write-Host "Runs only while you are logged on, as $principalName (no elevation)." -ForegroundColor DarkGray

    if (-not $NoStart) {
        Start-ScheduledTask -TaskName $TaskName
        Write-Host 'Started. The microphone is now active locally.' -ForegroundColor Yellow
    }
    Write-Host "Log: $logFile" -ForegroundColor DarkGray
    Write-Host "Stop it with: .\scripts\install-aether-voice-service.ps1 -Action Stop" -ForegroundColor DarkGray
}

function Uninstall-VoiceService {
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($null -eq $task) {
        Write-Host 'AETHER voice service is not installed.' -ForegroundColor Yellow
        return
    }
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Stop-VoiceServiceProcesses
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed $TaskName" -ForegroundColor Green
}

function Show-Status {
    $null = Get-AetherTask
    $info = Get-ScheduledTaskInfo -TaskName $TaskName
    $task = Get-ScheduledTask -TaskName $TaskName
    $processes = @(Get-VoiceServiceProcesses)
    # The venv pythonw.exe is a stub that spawns the real base-interpreter
    # worker, so one service instance normally shows two processes.
    $workers = @($processes | Where-Object { $_.ExecutablePath -and $_.ExecutablePath -ne $pythonw })
    [pscustomobject]@{
        Name           = $task.TaskName
        State          = $task.State
        VoiceProcesses = $workers.Count
        LastRunTime    = $info.LastRunTime
        LastTaskResult = $info.LastTaskResult
        NextRunTime    = $info.NextRunTime
    } | Format-List
    if ($workers.Count -gt 1) {
        Write-Host "WARNING: $($workers.Count) voice workers are competing for the microphone. Run -Action Restart." -ForegroundColor Yellow
    }

    if (Test-Path -LiteralPath $statusFile) {
        Write-Host 'Runtime status:' -ForegroundColor Cyan
        Get-Content -LiteralPath $statusFile
    } else {
        Write-Host 'No runtime status file yet.' -ForegroundColor Yellow
    }
}

function Show-Logs {
    if (-not (Test-Path -LiteralPath $logFile)) {
        Write-Host "No log file yet at $logFile" -ForegroundColor Yellow
        return
    }
    Get-Content -LiteralPath $logFile -Tail 80
}

switch ($Action) {
    'Install' { Install-VoiceService }
    'Uninstall' { Uninstall-VoiceService }
    'Start' {
        $null = Get-AetherTask
        Stop-VoiceServiceProcesses
        Start-ScheduledTask -TaskName $TaskName
        Write-Host 'AETHER voice service started.' -ForegroundColor Green
    }
    'Stop' {
        $null = Get-AetherTask
        Stop-ScheduledTask -TaskName $TaskName
        Stop-VoiceServiceProcesses
        Write-Host 'AETHER voice service stopped; microphone released.' -ForegroundColor Green
    }
    'Restart' {
        $null = Get-AetherTask
        Stop-ScheduledTask -TaskName $TaskName
        Stop-VoiceServiceProcesses
        Start-ScheduledTask -TaskName $TaskName
        Write-Host 'AETHER voice service restarted.' -ForegroundColor Green
    }
    'Status' { Show-Status }
    'Logs' { Show-Logs }
    'Doctor' { & $python $cli doctor }
}
