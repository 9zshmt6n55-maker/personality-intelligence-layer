$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = (Get-Command python).Source

Get-CimInstance Win32_Process |
    Where-Object { $_.Name -like 'python*' -and $_.CommandLine -match 'desktop_orb\.py\s+--size' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

& $python "pkm_signal.py" "off" | Out-Null

Start-Process -FilePath $python `
    -ArgumentList "desktop_orb.py --size 112 --opacity 0.88" `
    -WorkingDirectory $Root `
    -WindowStyle Hidden
