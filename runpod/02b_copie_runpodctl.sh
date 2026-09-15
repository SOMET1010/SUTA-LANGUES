#!/usr/bin/env bash
# 02b — SECOURS : si les deux pods ne peuvent pas se joindre en SSH direct.
# runpodctl envoie en pair-a-pair, dossier par dossier, via une archive temporaire.
# ATTENTION : demande de la place libre sur le pod source (taille de l archive).
# Aucune suppression : l archive temporaire est a effacer A LA MAIN apres verification.
set -euo pipefail

DIR="${1:?usage: ./02b_copie_runpodctl.sh /workspace/SUTA-LANGUES}"
STAGE="${STAGE:-/workspace/_transit}"
NAME="$(basename "$DIR")"

command -v runpodctl >/dev/null || { echo "runpodctl absent sur ce pod"; exit 1; }
mkdir -p "$STAGE"
df -h "$STAGE"
echo "Taille de $DIR :"; du -sh "$DIR"
echo "Poursuivre ? Ctrl-C pour annuler."; read -r _

tar -C "$(dirname "$DIR")" -czf "$STAGE/$NAME.tar.gz" "$NAME"
sha256sum "$STAGE/$NAME.tar.gz" | tee "$STAGE/$NAME.tar.gz.sha256"
echo
echo ">>> Sur le pod DESTINATION, lancer : runpodctl receive <code affiche ci-dessous>"
runpodctl send "$STAGE/$NAME.tar.gz"
echo
echo "Cote destination, apres reception :"
echo "  sha256sum -c $NAME.tar.gz.sha256   # le sha doit correspondre"
echo "  tar -C /workspace -xzf $NAME.tar.gz"
echo
echo "NE PAS supprimer $STAGE tant que 03_verification.sh nest pas passe au vert."
