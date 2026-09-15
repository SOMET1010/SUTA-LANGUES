#!/usr/bin/env bash
# 06_s3_restauration.sh — NOUVEAU pod GPU (EU-RO-1, volume monte sur /workspace).
# Deballe les archives deposees par 05_s3_sauvegarde.sh. Elles sont deja sur le
# volume (le bucket S3 EST le volume) : pas de retelechargement reseau.
# Ne supprime aucune archive : cest 03_verification.sh puis toi qui decidez.
set -euo pipefail

WS="${WS:-/workspace}"
PREFIX="${PREFIX:-_sauvegarde}"
SRC="$WS/$PREFIX"

[ -d "$SRC" ] || { echo "ECHEC : $SRC introuvable. Le volume est-il bien monte sur $WS ?"; exit 1; }

echo "--- archives disponibles ---"
ls -lah "$SRC"
echo
echo "--- espace libre ---"
df -h "$WS"
echo
echo "Le deballage ecrit dans $WS. Ctrl-C pour annuler, Entree pour continuer."
read -r _

for T in "$SRC"/*.tar.gz; do
  [ -f "$T" ] || continue
  NAME="$(basename "$T" .tar.gz)"
  if [ -e "$WS/$NAME" ]; then
    echo "IGNORE : $WS/$NAME existe deja (rien ecrase)."
    continue
  fi
  echo "--- extraction $NAME ---"
  tar -C "$WS" -xzf "$T"
  echo "OK  $WS/$NAME"
done

for F in maliba-test.wav suta-langues.log; do
  [ -f "$SRC/$F" ] && [ ! -e "$WS/$F" ] && cp -a "$SRC/$F" "$WS/$F" && echo "OK  $WS/$F"
done

echo
echo "=== Deballage termine. Lancer maintenant 03_verification.sh. ==="
echo "Ne supprimer $SRC quapres verification verte ET accord explicite."
