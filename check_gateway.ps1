param(
  [string]$GatewayUrl = "",
  [string]$AgentId = ""
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

function Read-StatusCandidate {
  $statusPath = Join-Path $PSScriptRoot "PDK_PUBLIC_GATEWAY_STATUS.json"
  if (-not (Test-Path -LiteralPath $statusPath)) {
    throw "PDK_PUBLIC_GATEWAY_STATUS.json not found"
  }
  Get-Content -Raw -Encoding UTF8 -LiteralPath $statusPath | ConvertFrom-Json
}

function Invoke-Probe {
  param(
    [string]$Url,
    [string]$Label
  )
  try {
    $result = Invoke-RestMethod -Uri $Url -Method Get -TimeoutSec 20
    [ordered]@{
      label = $Label
      url = $Url
      ok = $true
      schema = $result.schema
      status = $result.status
    }
  } catch {
    [ordered]@{
      label = $Label
      url = $Url
      ok = $false
      error = $_.Exception.Message
    }
  }
}

$status = Read-StatusCandidate
if (-not $GatewayUrl) {
  $GatewayUrl = [string]$status.public_url
}
$GatewayUrl = $GatewayUrl.TrimEnd("/")
if (-not $GatewayUrl) {
  throw "No gateway URL was provided and public_url is empty"
}

$updatedAt = $null
try { $updatedAt = [datetimeoffset]::Parse([string]$status.updated_at) } catch {}
$ageMinutes = if ($updatedAt) { [math]::Round(([datetimeoffset]::Now - $updatedAt).TotalMinutes, 1) } else { $null }
$staleAfter = if ($status.stale_after_minutes) { [int]$status.stale_after_minutes } else { 120 }

$diagnoseUrl = "$GatewayUrl/api/external/diagnose"
if ($AgentId) {
  $diagnoseUrl = "$diagnoseUrl?agent_id=$([uri]::EscapeDataString($AgentId))"
}

$probes = @(
  Invoke-Probe "$GatewayUrl/api/health" "health"
  Invoke-Probe "$GatewayUrl/api/external/spec" "spec"
  Invoke-Probe $diagnoseUrl "diagnose"
  Invoke-Probe "$GatewayUrl/api/external/society" "society"
)

$ok = -not ($probes | Where-Object { -not $_.ok } | Select-Object -First 1)

[ordered]@{
  ok = $ok
  gateway_url = $GatewayUrl
  status_updated_at = $status.updated_at
  status_age_minutes = $ageMinutes
  stale_after_minutes = $staleAfter
  stale_by_snapshot_age = if ($ageMinutes -ne $null) { $ageMinutes -gt $staleAfter } else { $true }
  candidate_only = if ($status.candidate_only -ne $null) { [bool]$status.candidate_only } else { $true }
  rule = "Use this URL only if probes are ok. If probes fail, stop using the URL; do not use localhost unless you are on the host machine."
  probes = $probes
} | ConvertTo-Json -Depth 20
