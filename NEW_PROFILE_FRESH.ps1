param(
    [string]$Profile = ""
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
if ($Profile -eq "") {
    $Profile = Read-Host "New profile slug, for example test-agent"
}
if ($Profile -eq "") {
    Write-Host "No profile provided." -ForegroundColor Yellow
    exit 1
}

$python = (Get-Command python).Source

Push-Location $Root
try {
    & $python ".\pil_profiles.py" "boot" "--profile" $Profile "--mode" "fresh" "--reset"
}
finally {
    Pop-Location
}
