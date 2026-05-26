$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$port = 8790
$hostAddress = "0.0.0.0"

Write-Host "Starting PDK External Agent Gateway..."
Write-Host "Local machine: http://127.0.0.1:$port/"
Write-Host "LAN address:   http://192.168.31.35:$port/"
Write-Host "Agent spec:    http://192.168.31.35:$port/api/external/spec"
Write-Host ""
Write-Host "This gateway disables admin POST actions and only allows external agent endpoints."

python society_observatory.py --host $hostAddress --port $port --agent-gateway
