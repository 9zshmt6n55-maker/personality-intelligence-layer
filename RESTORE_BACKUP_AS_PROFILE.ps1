param(
    [string]$Backup = ""
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Desktop = [Environment]::GetFolderPath("Desktop")
$Downloads = Join-Path ([Environment]::GetFolderPath("UserProfile")) "Downloads"

if ($Backup -eq "") {
    $candidates = @(
        (Join-Path $Root "PIL_PERSONALITY_BACKUP.md"),
        (Join-Path $Desktop "PIL_PERSONALITY_BACKUP.md"),
        (Join-Path $Downloads "PIL_PERSONALITY_BACKUP.md"),
        (Join-Path $Root "imports\PIL_PERSONALITY_BACKUP.md")
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            $Backup = $candidate
            break
        }
    }
}

if ($Backup -eq "" -or -not (Test-Path -LiteralPath $Backup)) {
    Write-Host "PIL_PERSONALITY_BACKUP.md not found." -ForegroundColor Yellow
    Write-Host "Put it beside this script, on Desktop, in Downloads, or pass -Backup <path>."
    Read-Host "Press Enter to exit"
    exit 1
}

$python = (Get-Command python).Source

Push-Location $Root
try {
    & $python ".\pil_profiles.py" "restore-backup" $Backup "--open"
}
finally {
    Pop-Location
}
