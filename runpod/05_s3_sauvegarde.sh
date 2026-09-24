#!/usr/bin/env bash
# 05_s3_sauvegarde.sh — ANCIEN pod (demarre en CPU) -> Network Volume via API S3.
# Le bucket S3 EST le Network Volume : ce qui est ecrit ici sera visible sur le
# futur pod GPU sous /workspace.
#
# Chaque dossier part en archive tar.gz (preserve liens symboliques, droits,
# bit executable — ce quun sync S3 brut perdrait, ce qui casserait le venv).
# Par defaut larchive est STREAMEE : aucun espace disque consomme sur le pod.
#
# Prerequis : cle S3 creee dans RunPod (Settings -> S3 API Keys), exportee en
#   AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY.
#
# LECTURE SEULE cote source : rien nest supprime ni modifie dans /workspace.
set -euo pipefail

BUCKET="${BUCKET:-vn82f9ix44}"
ENDPOINT="${ENDPOINT:-https://s3api-eu-ro-1.runpod.io}"
REGION="${REGION:-eu-ro-1}"
PREFIX="${PREFIX:-_sauvegarde}"
WS="${WS:-/workspace}"

: "${AWS_ACCESS_KEY_ID:?exporter AWS_ACCESS_KEY_ID (cle S3 RunPod)}"
: "${AWS_SECRET_ACCESS_KEY:?exporter AWS_SECRET_ACCESS_KEY (cle S3 RunPod)}"

S3() { aws s3 --region "$REGION" --endpoint-url "$ENDPOINT" "$@"; }

command -v aws >/dev/null || { echo "aws absent : pip install awscli"; exit 1; }

CIBLES=("${@:-}")
if [ -z "${1:-}" ]; then
  CIBLES=("$WS/maliba-venv" "$WS/SUTA-LANGUES" "$WS/Spark-TTS")
fi

echo "=== Sauvegarde vers s3://$BUCKET/$PREFIX/ ==="
echo "--- test de connexion ---"
S3 ls "s3://$BUCKET/" || { echo "ECHEC : bucket injoignable, verifier les cles"; exit 1; }
echo

for DIR in "${CIBLES[@]}"; do
  [ -d "$DIR" ] || { echo "IGNORE (absent) : $DIR"; continue; }
  NAME="$(basename "$DIR")"
  echo "--- $DIR ($(du -sh "$DIR" | cut -f1)) -> s3://$BUCKET/$PREFIX/$NAME.tar.gz"
  tar -C "$(dirname "$DIR")" --warning=no-file-changed -czf - "$NAME" \
    | S3 cp - "s3://$BUCKET/$PREFIX/$NAME.tar.gz" --expected-size 0 2>/dev/null \
    || tar -C "$(dirname "$DIR")" --warning=no-file-changed -czf - "$NAME" \
       | S3 cp - "s3://$BUCKET/$PREFIX/$NAME.tar.gz"
  echo "OK  $NAME"
done

echo
echo "--- petits fichiers en clair ---"
for F in "$WS/maliba-test.wav" "$WS/suta-langues.log"; do
  [ -f "$F" ] && S3 cp "$F" "s3://$BUCKET/$PREFIX/$(basename "$F")" && echo "OK  $(basename "$F")"
done
[ -d "$WS/_inventaire" ] && S3 cp --recursive "$WS/_inventaire" "s3://$BUCKET/$PREFIX/_inventaire/"

echo
echo "--- contenu depose sur le volume ---"
S3 ls --recursive --human-readable "s3://$BUCKET/$PREFIX/"
echo
echo "=== Termine. Rien na ete supprime sur lancien pod. ==="
echo "Etape suivante : pod GPU en EU-RO-1 avec le volume monte sur /workspace,"
echo "puis 06_s3_restauration.sh."
