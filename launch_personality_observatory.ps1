param(
    [switch]$KeepExisting,
    [string]$AgentId = "default",
    [string]$Visible = "",
    [string]$Signal = "",
    [string]$Ready = "",
    [int]$X = -1,
    [int]$Y = -1,
    [switch]$Compact
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = (Get-Command python).Source

if ($Visible -eq "") {
    $Visible = Join-Path $Root "public\pkm_visible.json"
}
if ($Signal -eq "") {
    $Signal = Join-Path $Root "state\orb_signal.json"
}
if ($Ready -eq "") {
    $Ready = Join-Path $Root "state\orb_ready.json"
}
if ($AgentId -eq "") {
    $AgentId = "default"
}

if (-not $KeepExisting) {
    $escapedAgent = [regex]::Escape($AgentId)
    $escapedVisible = [regex]::Escape($Visible)
    Get-CimInstance Win32_Process |
        Where-Object {
            $_.Name -like 'python*' -and
            $_.CommandLine -match 'desktop_orb\.py' -and
            (
                ($_.CommandLine -match '--agent-id' -and $_.CommandLine -match $escapedAgent) -or
                ($_.CommandLine -match '--visible' -and $_.CommandLine -match $escapedVisible)
            )
        } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}

& $python "pkm_signal.py" "off" "--file" $Signal | Out-Null

$orbArgs = @(
    "desktop_orb.py",
    "--agent-id", $AgentId,
    "--size", "112",
    "--opacity", "0.94",
    "--visible", $Visible,
    "--signal", $Signal,
    "--ready", $Ready
)

if (-not $Compact) {
    $orbArgs += "--console"
}
if ($X -ge 0) {
    $orbArgs += @("--x", "$X")
}
if ($Y -ge 0) {
    $orbArgs += @("--y", "$Y")
}

Start-Process -FilePath $python `
    -ArgumentList $orbArgs `
    -WorkingDirectory $Root `
    -WindowStyle Hidden
