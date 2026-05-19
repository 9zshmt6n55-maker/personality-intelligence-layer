param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = (Get-Command python).Source
$state = Join-Path $Root "state\agent.pkm.json"

if ((Test-Path -LiteralPath $state) -and -not $Force) {
    try {
        $payload = Get-Content -Raw -LiteralPath $state | ConvertFrom-Json
        if ($null -ne $payload.manifest.pil_backup) {
            Write-Host "Refusing to open legacy default because root state contains an imported PIL backup." -ForegroundColor Yellow
            Write-Host "This root file may already be a restored agent. Use profiles instead:"
            Write-Host "  python .\pil_profiles.py list"
            Write-Host "  python .\pil_profiles.py boot --profile <profile> --mode continue"
            Write-Host "Use -Force only if you intentionally want the root legacy state."
            exit 1
        }
    }
    catch {
        Write-Host "Could not inspect root legacy state. Refusing without -Force." -ForegroundColor Yellow
        exit 1
    }
}

Push-Location $Root
try {
    & $python ".\pkm_runtime.py" "boot" "--mode" "continue"
}
finally {
    Pop-Location
}
