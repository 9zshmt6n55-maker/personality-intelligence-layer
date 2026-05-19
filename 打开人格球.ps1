$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = (Get-Command python).Source

if (-not (Test-Path -LiteralPath (Join-Path $Root "pkm_runtime.py"))) {
    Write-Host "pkm_runtime.py not found. Run this script inside the PIL folder." -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

Push-Location $Root
try {
    & $python ".\pkm_runtime.py" "boot" "--mode" "continue"
}
finally {
    Pop-Location
}
