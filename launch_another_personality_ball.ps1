param(
    [string]$Profile = ""
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$stamp = Get-Date -Format "yyyyMMdd_HHmmss_fff"
if ($Profile -eq "") {
    $Profile = "ad-hoc-$stamp"
}

$signal = Join-Path $Root "state\orb_signal_$stamp.json"
$x = Get-Random -Minimum 80 -Maximum 460
$y = Get-Random -Minimum 80 -Maximum 320

& (Join-Path $Root "launch_personality_observatory.ps1") `
    -KeepExisting `
    -AgentId $Profile `
    -Compact `
    -Signal $signal `
    -X $x `
    -Y $y
