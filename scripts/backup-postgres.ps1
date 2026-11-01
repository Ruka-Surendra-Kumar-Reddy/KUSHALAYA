# Backup PostgreSQL using pg_dump. Requires pg_dump on PATH and DATABASE_URL or PG* env vars.
# Linux/production: use scripts/deploy/backup-safehome-postgres.sh (see docs/deploy/POSTGRES_BACKUP.md).
param(
    [string]$DatabaseUrl = $env:DATABASE_URL,
    [string]$BackupDir = "backups"
)

$ErrorActionPreference = "Stop"
if (-not $DatabaseUrl) {
    Write-Error "Set DATABASE_URL (postgresql://user:pass@host:5432/dbname)"
}

$ts = Get-Date -Format "yyyyMMdd-HHmmss"
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
$dest = Join-Path $BackupDir "safehomeops-$ts.sql.gz"

# pg_dump reads connection from URI when using --dbname
pg_dump --dbname=$DatabaseUrl --format=plain --no-owner | gzip > $dest
Write-Host "Backup created: $dest"
