# Backup SQLite database (development). Usage: .\scripts\backup-sqlite.ps1
param(
    [string]$DbPath = "backend\eldercareops.db",
    [string]$BackupDir = "backups"
)

$ErrorActionPreference = "Stop"
$ts = Get-Date -Format "yyyyMMdd-HHmmss"
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
$dest = Join-Path $BackupDir "eldercareops-$ts.db"

if (-not (Test-Path $DbPath)) {
    Write-Error "Database not found: $DbPath"
}

Copy-Item $DbPath $dest
Write-Host "Backup created: $dest"
