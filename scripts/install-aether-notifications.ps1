[CmdletBinding()]
param([switch]$Remove)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$taskName = "AETHER Personal Assistant Notifications"
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"

if ($Remove) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "AETHER notification startup task removed."
    exit 0
}

if (-not (Test-Path $python)) {
    throw "AETHER virtual environment was not found. Run the Windows installer first."
}

$action = New-ScheduledTaskAction -Execute $python -Argument "-m app.windows_notifications" -WorkingDirectory $repoRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
$task = New-ScheduledTask -Action $action -Trigger $trigger -Settings $settings -Principal $principal
Register-ScheduledTask -TaskName $taskName -InputObject $task -Force | Out-Null
Start-ScheduledTask -TaskName $taskName
Write-Host "AETHER Windows notifications are configured to start at sign-in."
Write-Host "Remove with: .\scripts\install-aether-notifications.ps1 -Remove"
