#Requires -Version 5.1
[CmdletBinding()]
param(
    [string]$Python = 'C:\Users\Ashok Kunchala\AppData\Local\Temp\opencode\aether-venv\Scripts\python.exe',
    [string]$BindHost = '127.0.0.1',
    [int]$Port = 8000
)

$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Python interpreter not found: $Python"
}

Set-Location -LiteralPath $RepoRoot

# Credentials stay in the gitignored .env; these are runtime-only model overrides.
$env:AETHER_AI_PROVIDER = 'nvidia'
$env:OPENROUTER_MODEL = 'baidu/ernie-5.5-flash-preview:free'
$env:GROQ_MODEL = 'qwen/qwen3.8-27b'
$env:NVIDIA_MODEL = 'minimaxai/minimax-m3.1-flash'

Write-Host "AETHER local: provider order nvidia > gemini > openrouter > groq on ${BindHost}:${Port}"

& $Python -m uvicorn app.main_enhanced:app --host $BindHost --port $Port --no-access-log
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
