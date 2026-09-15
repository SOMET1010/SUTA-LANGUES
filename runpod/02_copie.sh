#!/usr/bin/env bash
# 02_copie.sh — copie ANCIEN pod -> NOUVEAU pod (Network Volume monte sur /workspace).
# A lancer sur le NOUVEAU pod : on TIRE les donnees (pull). Aucune ecriture sur le pod source.
# Aucun --delete : rsync ne supprime jamais rien ici.
#
# Usage :
#   SRC_HOST=1.2.3.4 SRC_PORT=22001 ./02_copie.sh --dry-run   # simulation
#   SRC_HOST=1.2.3.4 SRC_PORT=22001 ./02_copie.sh             # copie reelle (relancable)
set -euo pipefail

: "${SRC_HOST:?definir SRC_HOST = IP publique du pod source}"
SRC_PORT="${SRC_PORT:-22}"
SRC_USER="${SRC_USER:-root}"
SRC_DIR="${SRC_DIR:-/workspace/}"
DST_DIR="${DST_DIR:-/workspace/}"
KEY="${KEY:-$HOME/.ssh/id_ed25519}"

DRY=""
if [ "${1:-}" = "--dry-run" ]; then DRY="--dry-run"; fi

command -v rsync >/dev/null || { echo "rsync manquant : apt-get update && apt-get install -y rsync"; exit 1; }

echo "Source      : $SRC_USER@$SRC_HOST:$SRC_PORT$SRC_DIR"
echo "Destination : $DST_DIR  (doit etre le Network Volume)"
findmnt -T "$DST_DIR" || true
df -h "$DST_DIR"
echo
if [ -n "$DRY" ]; then echo ">>> MODE SIMULATION : rien ne sera ecrit."; fi

rsync -aHAX --numeric-ids --partial --info=progress2 --human-readable $DRY \
  -e "ssh -p $SRC_PORT -i $KEY -o StrictHostKeyChecking=accept-new" \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude '.cache/' \
  --exclude '_inventaire/' \
  "$SRC_USER@$SRC_HOST:$SRC_DIR" "$DST_DIR"

echo
echo "=== Copie terminee. Etape suivante : 03_verification.sh ==="
