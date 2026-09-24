#!/usr/bin/env bash
# 01_inventaire.sh — LECTURE SEULE. Aucune suppression, aucune écriture hors de $OUT.
# A lancer sur l'ANCIEN pod (et plus tard sur le NOUVEAU, pour comparer).
set -euo pipefail

WS="${WS:-/workspace}"
OUT="${OUT:-/workspace/_inventaire}"
TAG="${TAG:-$(hostname)-$(date -u +%Y%m%dT%H%M%SZ)}"
MAN="$OUT/manifeste-$TAG.txt"

mkdir -p "$OUT"
exec > >(tee "$OUT/inventaire-$TAG.log") 2>&1

echo "=== INVENTAIRE $TAG ==="
echo "--- espace disque ---"
df -h "$WS" || true
echo
echo "--- point de montage de $WS ---"
findmnt -T "$WS" 2>/dev/null || mount | grep -E " on ${WS} " || true
echo
echo "--- contenu racine ---"
ls -la "$WS"
echo
echo "--- taille par entree (peut prendre 1-2 min) ---"
du -sh "$WS"/* 2>/dev/null | sort -h
echo
echo "--- presence des elements critiques ---"
for p in \
  "$WS/SUTA-LANGUES" \
  "$WS/Spark-TTS" \
  "$WS/maliba-venv" \
  "$WS/SUTA-LANGUES/Spark-TTS-0.5B" \
  "$WS/maliba-test.wav" \
  "$WS/suta-langues.log"
do
  if [ -e "$p" ]; then
    n=$(find "$p" -type f 2>/dev/null | wc -l)
    b=$(du -sb "$p" 2>/dev/null | cut -f1)
    printf 'OK      %-45s fichiers=%-7s octets=%s\n' "$p" "$n" "$b"
  else
    printf 'ABSENT  %s\n' "$p"
  fi
done
echo
echo "--- poids du modele Spark-TTS-0.5B ---"
find "$WS/SUTA-LANGUES/Spark-TTS-0.5B" -maxdepth 2 -type f \
     \( -name '*.safetensors' -o -name '*.bin' -o -name '*.pt' -o -name '*.onnx' -o -name '*.json' \) \
     -printf '%10s  %p\n' 2>/dev/null | sort -k2 || echo "(dossier modele introuvable)"
echo
echo "--- venv: python et paquets cles ---"
if [ -x "$WS/maliba-venv/bin/python" ]; then
  "$WS/maliba-venv/bin/python" -V
  "$WS/maliba-venv/bin/pip" list 2>/dev/null | grep -Ei '^(torch|torchaudio|gradio|gradio-client|pydantic|transformers|numpy|soundfile) ' || true
  echo "--- pip check ---"
  "$WS/maliba-venv/bin/pip" check || echo "(conflits signales ci-dessus)"
  echo "--- nb total de paquets ---"
  "$WS/maliba-venv/bin/pip" list 2>/dev/null | wc -l
else
  echo "(venv absent ou non executable)"
fi
echo
echo "--- GPU ---"
nvidia-smi 2>/dev/null || echo "(pas de GPU visible sur ce pod)"
echo
echo "--- manifeste (chemin + taille + mtime de chaque fichier) ---"
find "$WS" -path "$OUT" -prune -o -type f -printf '%s\t%TY-%Tm-%Td\t%p\n' 2>/dev/null \
  | grep -v '__pycache__' | sort -k3 > "$MAN"
wc -l "$MAN"
echo "Manifeste ecrit dans : $MAN"
echo
echo "--- empreintes SHA256 des fichiers critiques (hors venv, trop long) ---"
find "$WS/SUTA-LANGUES" "$WS/Spark-TTS" -maxdepth 3 -type f \
     \( -name '*.safetensors' -o -name '*.bin' -o -name '*.pt' -o -name '*.py' -o -name '*.json' -o -name '*.yaml' \) \
     -size +0 2>/dev/null | sort | head -200 | xargs -r sha256sum > "$OUT/sha256-$TAG.txt" || true
[ -f "$WS/maliba-test.wav" ] && sha256sum "$WS/maliba-test.wav" >> "$OUT/sha256-$TAG.txt"
wc -l "$OUT/sha256-$TAG.txt" 2>/dev/null || true
echo
echo "=== FIN INVENTAIRE — rien n'a ete supprime ni modifie hors de $OUT ==="
