#!/usr/bin/env bash
# Sauvegarde chiffrée de Postgres vers Cloudflare R2. Cron quotidien sur le VPS.
set -euo pipefail

cd "$(dirname "$0")/../.."                      # racine du repo
# shellcheck disable=SC1091
source deploy/backup/backup.env                 # AGE_RECIPIENT, R2_BUCKET, RCLONE_CONFIG

STAMP="$(date -u +%F)"
OUT_DIR="backups/db"
mkdir -p "$OUT_DIR"
FILE="$OUT_DIR/db-$STAMP.sql.gz.age"

echo "==> Dump + chiffrement -> $FILE"
docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U postgres --no-owner ats_diagnostic \
  | gzip \
  | age -r "$AGE_RECIPIENT" > "$FILE"

test -s "$FILE" || { echo "!! dump vide"; exit 1; }

echo "==> Upload R2"
rclone --config "$RCLONE_CONFIG" copy "$FILE" "r2:$R2_BUCKET/db/"

echo "==> Prune local (> 21 jours)"
find "$OUT_DIR" -name 'db-*.sql.gz.age' -mtime +21 -delete

echo "==> Prune R2 (> 60 jours)"
rclone --config "$RCLONE_CONFIG" delete --min-age 60d "r2:$R2_BUCKET/db/"

echo "OK $STAMP"
