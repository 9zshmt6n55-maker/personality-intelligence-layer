param(
    [int]$Port = 8787,
    [switch]$KeepExisting
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = (Get-Command python).Source

if (-not $KeepExisting) {
    Get-CimInstance Win32_Process |
        Where-Object {
            $_.Name -like 'python*' -and
            $_.CommandLine -match 'society_observatory\.py'
        } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}

$argsList = @(
    "society_observatory.py",
    "--host", "127.0.0.1",
    "--port", "$Port"
)

Start-Process -FilePath $python `
    -ArgumentList $argsList `
    -WorkingDirectory $Root `
    -WindowStyle Hidden

Start-Sleep -Milliseconds 700
Start-Process "http://127.0.0.1:$Port/"
