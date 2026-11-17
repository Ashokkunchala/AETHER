#Requires -Version 5.1
<#
.SYNOPSIS
    Build JARVIS-Setup.exe - a single-click Windows installer executable.

.DESCRIPTION
    Compiles a small console launcher with the offline .NET Framework C#
    compiler (csc.exe, present on every Windows 10/11 machine - no PyInstaller,
    no ps2exe, no network needed for the build) that embeds INSTALL-JARVIS.ps1
    as base64:

      1. Reads INSTALL-JARVIS.ps1 as raw bytes and embeds them (byte-perfect).
      2. The generated JARVIS-Setup.exe, when double-clicked, writes the
         embedded script to %TEMP%\jarvis-setup-<guid>\, runs it with
         powershell.exe -NoProfile -ExecutionPolicy Bypass, waits, forwards
         the child's exit code, and always cleans up its temp directory.
      3. The window stays open at the end (any-key pause) unless
         JARVIS_SETUP_NO_PAUSE=1 is set or the output is redirected, so an
         unattended run can never hang.

    The embedded installer is the tested one: it finds/installs Python 3.11+,
    downloads the current branch from GitHub, creates .venv, installs
    dependencies, writes .env (asks for your API key), registers the sign-in
    task, runs "jarvis doctor" and starts JARVIS.

    Because the payload downloads the published branch, push your commits
    before distributing the exe.

.PARAMETER OutFile
    Output executable path. Default: <repo>\dist\JARVIS-Setup.exe.

.PARAMETER InstallerPath
    PowerShell installer to embed. Default: <repo>\INSTALL-JARVIS.ps1.

.PARAMETER CscPath
    Explicit path to csc.exe. Auto-detected (Framework64, then Framework).

.PARAMETER SelfTest
    Additionally compile a throwaway probe exe, run it, and assert the
    extract -> run -> exit-code plumbing (probe exits 7 and prints a marker).

.PARAMETER KeepTemp
    Keep the intermediate .cs/.exe build files for debugging.

.EXAMPLE
    .\scripts\build-installer-exe.ps1 -SelfTest
    # Build dist\JARVIS-Setup.exe and prove the launcher plumbing works.

.EXAMPLE
    .\scripts\build-installer-exe.ps1 -OutFile "$env:USERPROFILE\Desktop\JARVIS-Setup.exe"
    # Build straight to the desktop for sharing.
#>
[CmdletBinding()]
param(
    [string]$OutFile = "",
    [string]$InstallerPath = "",
    [string]$CscPath = "",
    [switch]$SelfTest,
    [switch]$KeepTemp
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($OutFile)) { $OutFile = Join-Path $repoRoot "dist\JARVIS-Setup.exe" }
if ([string]::IsNullOrWhiteSpace($InstallerPath)) { $InstallerPath = (Join-Path $repoRoot "INSTALL-JARVIS.ps1") }

if (-not (Test-Path -LiteralPath $InstallerPath)) {
    throw "Installer script not found: $InstallerPath"
}
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot "scripts"))) {
    throw "Run this from the Jarvis-Personal-AI repository (expected <repo>\scripts)."
}

# ------------------------------------------------------------- 1. locate csc
$cscCandidates = @()
if (-not [string]::IsNullOrWhiteSpace($CscPath)) { $cscCandidates += $CscPath }
if ($env:WINDIR) {
    $cscCandidates += (Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe")
    $cscCandidates += (Join-Path $env:WINDIR "Microsoft.NET\Framework\v4.0.30319\csc.exe")
}
$csc = $cscCandidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
if (-not $csc) {
    throw "csc.exe not found. Install the .NET Framework 4.x (included with Windows 10/11) or pass -CscPath 'C:\path\to\csc.exe'."
}

# ------------------------------------------- 2. C# launcher template (C# 5)
# Marker is replaced with the base64 payload; String.Replace is used so the
# payload (A-Za-z0-9+/=) can never be treated as a regex.
$template = @'
using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;

[assembly: AssemblyTitle("AETHER Personal AI Setup")]
[assembly: AssemblyProduct("AETHER Personal AI")]
[assembly: AssemblyDescription("Single-click Windows installer for AETHER Personal AI")]
[assembly: AssemblyVersion("1.0.0.0")]
[assembly: AssemblyFileVersion("1.0.0.0")]

namespace JarvisSetup
{
    internal static class Program
    {
        private const string InstallerScriptName = "INSTALL-JARVIS.ps1";
        private const string InstallerScriptBase64 = "__SCRIPT_BASE64__";

        private static bool ShouldPause()
        {
            // Never block automated/CI runs; pause only for interactive humans.
            string flag = Environment.GetEnvironmentVariable("JARVIS_SETUP_NO_PAUSE");
            if (string.Equals(flag, "1", StringComparison.OrdinalIgnoreCase)) { return false; }
            try { if (Console.IsInputRedirected) { return false; } } catch { }
            return true;
        }

        private static int Main(string[] args)
        {
            string tempDir = Path.Combine(Path.GetTempPath(), "jarvis-setup-" + Guid.NewGuid().ToString("N"));
            int exitCode = 1;
            try
            {
                Directory.CreateDirectory(tempDir);
                string scriptPath = Path.Combine(tempDir, InstallerScriptName);
                File.WriteAllBytes(scriptPath, Convert.FromBase64String(InstallerScriptBase64));

                string powerShell = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.System),
                    "WindowsPowerShell", "v1.0", "powershell.exe");
                if (!File.Exists(powerShell)) { powerShell = "powershell.exe"; }

                string childArguments = "-NoProfile -ExecutionPolicy Bypass -File \"" + scriptPath + "\"";
                foreach (string argument in args)
                {
                    if (argument == null) { continue; }
                    childArguments += " \"" + argument.Replace("\"", "\\\"") + "\"";
                }

                Console.WriteLine("AETHER Personal AI - Setup");
                Console.WriteLine("Starting the Windows installer in this window...");
                Console.WriteLine();

                ProcessStartInfo startInfo = new ProcessStartInfo();
                startInfo.FileName = powerShell;
                startInfo.Arguments = childArguments;
                startInfo.UseShellExecute = false;
                startInfo.WorkingDirectory = Environment.CurrentDirectory;

                using (Process child = Process.Start(startInfo))
                {
                    if (child == null) { throw new InvalidOperationException("Could not start powershell.exe."); }
                    child.WaitForExit();
                    exitCode = child.ExitCode;
                }

                if (exitCode != 0)
                {
                    Console.Error.WriteLine();
                    Console.Error.WriteLine("Installer finished with exit code " + exitCode + ".");
                }
            }
            catch (Exception exception)
            {
                Console.Error.WriteLine("Setup failed: " +exception.Message);
                exitCode = 1;
            }
            finally
            {
                // The installer's own temp files live in its finally block; this
                // removes the extracted script even when the child was killed.
                try { if (Directory.Exists(tempDir)) { Directory.Delete(tempDir, true); } }
                catch { }
            }

            if (ShouldPause())
            {
                Console.WriteLine();
                Console.WriteLine("Press any key to close...");
                try { Console.ReadKey(true); } catch { }
            }
            return exitCode;
        }
    }
}
'@

function Build-LauncherExe {
    param(
        [Parameter(Mandatory = $true)][string]$PayloadText,
        [Parameter(Mandatory = $true)][string]$Destination
    )
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($PayloadText)
    $b64 = [Convert]::ToBase64String($bytes)
    $sourceText = $template.Replace("__SCRIPT_BASE64__", $b64)
    if ($sourceText.Contains("__SCRIPT_BASE64__")) { throw "Payload marker was not fully replaced." }

    $workDir = Join-Path $env:TEMP ("jarvis-exe-build-" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Force -Path $workDir | Out-Null
    $sourcePath = Join-Path $workDir "launcher.cs"

    # ASCII-safe (template and base64 are pure ASCII), written without BOM.
    [System.IO.File]::WriteAllText($sourcePath, $sourceText, [System.Text.UTF8Encoding]::new($false))

    $destDir = Split-Path -Parent $Destination
    if ($destDir -and -not (Test-Path -LiteralPath $destDir)) {
        New-Item -ItemType Directory -Force -Path $destDir | Out-Null
    }

    $cscOutput = & $csc /nologo /target:exe /optimize+ /platform:anycpu "/out:$Destination" $sourcePath 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "csc.exe failed (exit ${LASTEXITCODE}):`n$($cscOutput -join [Environment]::NewLine)"
    }
    if (-not (Test-Path -LiteralPath $Destination)) {
        throw "csc.exe reported success but $Destination was not created."
    }
    return $workDir
}

# ------------------------------------------------------------ 3. build exe
Write-Host ""
Write-Host "AETHER installer exe builder" -ForegroundColor Cyan
Write-Host "=============================" -ForegroundColor Cyan

$installerBytes = [System.IO.File]::ReadAllBytes($InstallerPath)
Write-Host "[PASS] csc.exe           : $csc" -ForegroundColor Green
Write-Host "[PASS] payload           : $InstallerPath ($($installerBytes.Length) bytes, embedded byte-perfect)"

$buildWorkDir = Build-LauncherExe -PayloadText ([System.Text.Encoding]::UTF8.GetString($installerBytes)) -Destination $OutFile

$exeItem = Get-Item -LiteralPath $OutFile
$hash = (Get-FileHash -LiteralPath $OutFile -Algorithm SHA256).Hash
Write-Host "[PASS] built             : $OutFile ($([math]::Round($exeItem.Length / 1KB, 1)) KB)" -ForegroundColor Green
Write-Host "[PASS] SHA256            : $hash" -ForegroundColor Green

# ------------------------------------------------------------- 4. self-test
$selfTestFailed = $false
if ($SelfTest) {
    Write-Host ""
    Write-Host "Self-test: compile + extract + run + exit-code plumbing..." -ForegroundColor Cyan
    $probeScript = "Write-Output 'JARVIS-SETUP-SELFTEST-OK'" + [Environment]::NewLine + "exit 7" + [Environment]::NewLine
    $probeExe = Join-Path $buildWorkDir "probe.exe"
    [void](Build-LauncherExe -PayloadText $probeScript -Destination $probeExe)

    $probeOut = Join-Path $buildWorkDir "probe.out.log"
    $probeErr = Join-Path $buildWorkDir "probe.err.log"
    $previousNoPause = $env:JARVIS_SETUP_NO_PAUSE
    $env:JARVIS_SETUP_NO_PAUSE = "1"
    try {
        $probe = Start-Process -FilePath $probeExe `
            -RedirectStandardOutput $probeOut -RedirectStandardError $probeErr `
            -PassThru -NoNewWindow -Wait
    } finally {
        if ($null -eq $previousNoPause) { Remove-Item Env:JARVIS_SETUP_NO_PAUSE -ErrorAction SilentlyContinue }
        else { $env:JARVIS_SETUP_NO_PAUSE = $previousNoPause }
    }

    $probeOutput = ""
    foreach ($log in @($probeOut, $probeErr)) {
        if (Test-Path -LiteralPath $log) { $probeOutput += (Get-Content -LiteralPath $log -Raw) }
    }
    if ($probe.ExitCode -ne 7) {
        Write-Host "[FAIL] probe exit code: expected 7, got $($probe.ExitCode)" -ForegroundColor Red
        $selfTestFailed = $true
    } elseif ($probeOutput -notmatch "JARVIS-SETUP-SELFTEST-OK") {
        Write-Host "[FAIL] probe stdout marker missing (child output was not captured)." -ForegroundColor Red
        $selfTestFailed = $true
    } else {
        Write-Host "[PASS] launcher extracted, ran the embedded script and forwarded exit code 7" -ForegroundColor Green
    }

    # The extracted temp dir must not survive the run.
    $leftovers = @(Get-ChildItem -Path (Join-Path $env:TEMP "jarvis-setup-*") -Directory -ErrorAction SilentlyContinue)
    if ($leftovers.Count -gt 0) {
        Write-Host "[FAIL] temp dirs left behind: $($leftovers.Name -join ', ')" -ForegroundColor Red
        $selfTestFailed = $true
    } else {
        Write-Host "[PASS] temp cleanup (no jarvis-setup-* directories left)" -ForegroundColor Green
    }
}

if (-not $KeepTemp) {
    Remove-Item -LiteralPath $buildWorkDir -Recurse -Force -ErrorAction SilentlyContinue
} else {
    Write-Host "[INFO] build files kept at $buildWorkDir" -ForegroundColor Yellow
}

Write-Host ""
if ($selfTestFailed) {
    Write-Host "BUILD FAILED (self-test)" -ForegroundColor Red
    exit 1
}
Write-Host "Done. Double-click $OutFile to review the AETHER installer." -ForegroundColor Green
Write-Host "Note: unsigned executable. Verify its source and hash; do not bypass an unexplained security warning." -ForegroundColor DarkGray
Write-Host "Note: behavior is determined by the embedded payload. Reviewed CI payloads use an exact source commit." -ForegroundColor DarkGray
exit 0
