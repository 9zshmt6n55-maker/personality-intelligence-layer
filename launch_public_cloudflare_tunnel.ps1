$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$cloudflaredCandidates = @(
  (Join-Path $PSScriptRoot "tools\cloudflared.exe"),
  "C:\Users\71003\Desktop\git\bazi_paid_app\tools\cloudflared.exe",
  "C:\Users\71003\Desktop\人格智能层\tools\cloudflared.exe"
)
$cloudflared = $cloudflaredCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $cloudflared) {
  $command = Get-Command cloudflared.exe -ErrorAction SilentlyContinue
  if ($command) {
    $cloudflared = $command.Source
  }
}
if (-not $cloudflared) {
  Write-Host "cloudflared.exe not found. Download it first:"
  Write-Host "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
  exit 1
}

$logDir = Join-Path $PSScriptRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$outLog = Join-Path $logDir "cloudflared_pdk_gateway.out.log"
$errLog = Join-Path $logDir "cloudflared_pdk_gateway.err.log"

Get-CimInstance Win32_Process |
  Where-Object { $_.Name -eq "cloudflared.exe" -and $_.CommandLine -like "*127.0.0.1:8790*" } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Remove-Item -LiteralPath $outLog, $errLog -Force -ErrorAction SilentlyContinue

$process = Start-Process -FilePath $cloudflared `
  -ArgumentList @("tunnel", "--url", "http://127.0.0.1:8790", "--no-autoupdate") `
  -WorkingDirectory $PSScriptRoot `
  -RedirectStandardOutput $outLog `
  -RedirectStandardError $errLog `
  -WindowStyle Hidden `
  -PassThru

Start-Sleep -Seconds 10
$combined = ""
if (Test-Path -LiteralPath $outLog) { $combined += Get-Content -Raw -Encoding UTF8 -LiteralPath $outLog }
if (Test-Path -LiteralPath $errLog) { $combined += "`n" + (Get-Content -Raw -Encoding UTF8 -LiteralPath $errLog) }
$publicUrl = [regex]::Match($combined, "https://[a-zA-Z0-9.-]+\.trycloudflare\.com").Value

$status = [ordered]@{
  schema = "pdk.public_gateway_status.v1"
  public_url = $publicUrl
  local_gateway = "http://127.0.0.1:8790"
  gateway_port = 8790
  process_id = $process.Id
  started_at = (Get-Date).ToString("s")
  spec = if ($publicUrl) { "$publicUrl/api/external/spec" } else { "" }
  society = if ($publicUrl) { "$publicUrl/api/external/society" } else { "" }
  join = if ($publicUrl) { "$publicUrl/api/external/join" } else { "" }
  action = if ($publicUrl) { "$publicUrl/api/external/action" } else { "" }
  note = "Temporary Cloudflare tunnel. If this URL fails, ask the host to relaunch launch_public_cloudflare_tunnel.ps1 and update this file."
}
$statusPath = Join-Path $PSScriptRoot "PDK_PUBLIC_GATEWAY_STATUS.json"
$statusJson = $status | ConvertTo-Json -Depth 5
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($statusPath, $statusJson + [Environment]::NewLine, $utf8NoBom)

Write-Host "PDK public tunnel process: $($process.Id)"
Write-Host "Public URL: $publicUrl"
Write-Host "Spec: $($status.spec)"
Write-Host "Logs: $errLog"
