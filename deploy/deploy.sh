#!/usr/bin/env bash
# Déploiement de la beta. À lancer sur le VPS, à la racine du repo cloné.
# Usage: deploy/deploy.sh [git-ref]
set -euo pipefail

REF="${1:-origin/main}"
COMPOSE="docker compose -f docker-compose.prod.yml"

echo "==> Fetch + checkout $REF"
git fetch --all --tags
git checkout --detach "$REF"
git log -1 --oneline

echo "==> Build + up"
$COMPOSE up -d --build

echo "==> Attente de /health (max 90s)"
for i in $(seq 1 18); do
  if curl -fsS http://127.0.0.1:8000/health | grep -q '"status":"ok"'; then
    echo "OK après $((i * 5))s"
    $COMPOSE ps
    exit 0
  fi
  sleep 5
done

echo "!! /health n'est jamais passé OK — logs :"
$COMPOSE logs --tail=80 backend
exit 1
