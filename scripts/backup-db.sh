#!/usr/bin/env bash
# PostgreSQL backup — integration point for the existing backup solution.
# Mounted into the postgres container by compose; run inside it:
#   docker compose exec postgres /usr/local/bin/backup-db.sh
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/backups/postgres}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
APP_DB="${POSTGRES_DB:-postgres}"

mkdir -p "$BACKUP_DIR"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_FILE="$BACKUP_DIR/${APP_DB}_${TIMESTAMP}.sql.gz"

pg_dump -U "$POSTGRES_USER" "$APP_DB" | gzip > "$BACKUP_FILE"

echo "Backup completed: $BACKUP_FILE"

# Retention: keep N days of backups, prune the rest.
find "$BACKUP_DIR" -name '*.sql.gz' -mtime "+$RETENTION_DAYS" -delete

echo "Pruned backups older than ${RETENTION_DAYS} days."