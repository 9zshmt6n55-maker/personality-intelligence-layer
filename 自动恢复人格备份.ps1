$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Desktop = [Environment]::GetFolderPath("Desktop")
$Parent = Split-Path -Parent $Root

$candidatePaths = @(
    (Join-Path $Root "PIL_PERSONALITY_BACKUP.md"),
    (Join-Path $Parent "PIL_PERSONALITY_BACKUP.md"),
    (Join-Path $Desktop "PIL_PERSONALITY_BACKUP.md"),
    (Join-Path $Root "imports\PIL_PERSONALITY_BACKUP.md")
) | Select-Object -Unique

$candidates = @()
foreach ($path in $candidatePaths) {
    if (Test-Path -LiteralPath $path) {
        $candidates += Get-Item -LiteralPath $path
    }
}

if ($candidates.Count -eq 0) {
    Write-Host "PIL_PERSONALITY_BACKUP.md not found." -ForegroundColor Yellow
    Write-Host "Put PIL_PERSONALITY_BACKUP.md on Desktop or in this folder, then run again."
    Read-Host "Press Enter to exit"
    exit 1
}

$backup = $candidates | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$python = (Get-Command python).Source

Push-Location $Root
try {
    & $python ".\pil_profiles.py" "restore-backup" $backup.FullName "--open"
    Write-Host "PIL backup restored into its own profile. Personality orb started." -ForegroundColor Green
    Write-Host "Backup: $($backup.FullName)"
}
finally {
    Pop-Location
}
