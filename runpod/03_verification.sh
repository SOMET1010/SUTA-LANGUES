#!/usr/bin/env bash
# 03_verification.sh — LECTURE SEULE. A lancer sur le NOUVEAU pod apres la copie.
# Compare avec le manifeste produit par 01_inventaire.sh sur le pod source.
# Sort en erreur si un element critique manque ou est vide.
set -euo pipefail

WS="${WS:-/workspace}"
SRC_MAN="${SRC_MAN:-}"   # chemin du manifeste-*.txt venant du pod source (optionnel)
ERR=0

echo "=== VERIFICATION $(date -u +%FT%TZ) ==="
findmnt -T "$WS" || true
df -h "$WS"
echo

check_dir() {
  local p="$1" min="$2"
  if [ ! -d "$p" ]; then echo "ECHEC   $p : absent"; ERR=1; return; fi
  local n b
  n=$(find "$p" -type f | wc -l)
  b=$(du -sb "$p" | cut -f1)
  if [ "$n" -lt "$min" ]; then
    echo "ECHEC   $p : seulement $n fichiers (attendu >= $min)"; ERR=1
  else
    printf 'OK      %-45s fichiers=%-7s octets=%s\n' "$p" "$n" "$b"
  fi
}

check_file() {
  local p="$1"
  if [ -s "$p" ]; then printf 'OK      %-45s octets=%s\n' "$p" "$(stat -c%s "$p")"
  else echo "ECHEC   $p : absent ou vide"; ERR=1; fi
}

check_dir "$WS/SUTA-LANGUES" 1
check_dir "$WS/Spark-TTS" 10
check_dir "$WS/maliba-venv" 100
check_dir "$WS/SUTA-LANGUES/Spark-TTS-0.5B" 3
check_file "$WS/maliba-test.wav"
echo

echo "--- poids du modele (doivent etre non vides) ---"
find "$WS/SUTA-LANGUES/Spark-TTS-0.5B" -type f \
     \( -name '*.safetensors' -o -name '*.bin' -o -name '*.pt' -o -name '*.onnx' \) \
     -printf '%10s  %p\n' 2>/dev/null | sort -k2 || { echo "ECHEC : aucun poids trouve"; ERR=1; }
echo

echo "--- venv utilisable ---"
if [ -x "$WS/maliba-venv/bin/python" ]; then
  "$WS/maliba-venv/bin/python" -V || ERR=1
  "$WS/maliba-venv/bin/pip" check || echo "ATTENTION : conflits pip signales"
  "$WS/maliba-venv/bin/python" - <<'PY' || ERR=1
import torch
print("torch", torch.__version__, "cuda dispo:", torch.cuda.is_available())
print("gpu:", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "aucun")
PY
else
  echo "ECHEC : $WS/maliba-venv/bin/python absent"; ERR=1
fi
echo

if [ -n "$SRC_MAN" ] && [ -f "$SRC_MAN" ]; then
  echo "--- diff avec le manifeste source ---"
  find "$WS" -path "$WS/_inventaire" -prune -o -type f -printf '%s\t%TY-%Tm-%Td\t%p\n' \
    | grep -v '__pycache__' | sort -k3 > /tmp/manifeste-dest.txt
  echo "source : $(wc -l < "$SRC_MAN") fichiers / destination : $(wc -l < /tmp/manifeste-dest.txt) fichiers"
  if diff <(cut -f1,3 "$SRC_MAN") <(cut -f1,3 /tmp/manifeste-dest.txt) > /tmp/diff-manifeste.txt; then
    echo "OK : manifestes identiques (chemin + taille)"
  else
    echo "DIFFERENCES (extrait, detail dans /tmp/diff-manifeste.txt) :"
    head -30 /tmp/diff-manifeste.txt
    ERR=1
  fi
else
  echo "(manifeste source non fourni : passer SRC_MAN=/chemin/manifeste-xxx.txt pour un diff exact)"
fi

echo
if [ "$ERR" -eq 0 ]; then
  echo "=== VERIFICATION OK — la copie est complete. Suppression de lancien pod possible APRES ton accord. ==="
else
  echo "=== VERIFICATION EN ECHEC — NE RIEN SUPPRIMER. Relancer 02_copie.sh (rsync est relancable). ==="
  exit 1
fi
