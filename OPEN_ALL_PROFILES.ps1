$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = (Get-Command python).Source

Push-Location $Root
try {
    & $python ".\pil_profiles.py" "open-all"
}
finally {
    Pop-Location
}
