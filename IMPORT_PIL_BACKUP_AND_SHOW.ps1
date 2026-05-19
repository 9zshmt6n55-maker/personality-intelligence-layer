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
        (Join-Path $Downloads "PIL_PERSONALITY_BACKUP.md")
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
    Write-Host "Put the backup beside this script, on Desktop, or in Downloads."
    Read-Host "Press Enter to exit"
    exit 1
}

if (-not (Test-Path -LiteralPath (Join-Path $Root "pil_profiles.py"))) {
    Write-Host "pil_profiles.py not found. Run this script inside the PIL folder." -ForegroundColor Yellow
    Write-Host "Current directory: $Root"
    Read-Host "Press Enter to exit"
    exit 1
}

$python = (Get-Command python).Source

Push-Location $Root
try {
    & $python ".\pil_profiles.py" "restore-backup" $Backup "--open"
    Write-Host "PIL backup imported into its own profile and personality orb started." -ForegroundColor Green
    Write-Host "Backup: $Backup"
}
finally {
    Pop-Location
}
