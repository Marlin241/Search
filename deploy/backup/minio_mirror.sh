#!/usr/bin/env bash
# Miroir du bucket MinIO 'personalization' vers Cloudflare R2.
# Cron quotidien sur le VPS.
set -euo pipefail

cd "$(dirname "$0")/../.."
# shellcheck disable=SC1091
source deploy/backup/backup.env   # R2_BUCKET, RCLONE_CONFIG, MINIO_ROOT_USER/PASSWORD

STAGE="backups/media"
mkdir -p "$STAGE"

# Export des objets MinIO vers un dossier local, via un conteneur mc jetable
# attaché au réseau interne (nom épinglé dans docker-compose.prod.yml).
docker run --rm --network search_internal \
  -e MC_USER="${MINIO_ROOT_USER:-minioadmin}" \
  -e MC_PASS="${MINIO_ROOT_PASSWORD:-minioadmin}" \
  -v "$(pwd)/$STAGE:/export" \
  --entrypoint sh minio/mc:latest -c '
    mc alias set src http://minio:9000 "$MC_USER" "$MC_PASS" >/dev/null &&
    mc mirror --overwrite --remove src/personalization /export
  '

echo "==> Sync vers R2"
rclone --config "$RCLONE_CONFIG" sync "$STAGE" "r2:$R2_BUCKET/media/"
echo "OK $(date -u +%F)"
