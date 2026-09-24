#!/usr/bin/env bash
# 04_relance_sparktts.sh — relance lUI Spark-TTS / MALIBA sur le port 7860.
# Reutilise lenvironnement existant : aucune reinstallation, aucun telechargement de modele.
set -euo pipefail

WS="${WS:-/workspace}"
VENV="${VENV:-$WS/maliba-venv}"
APP="${APP:-$WS/Spark-TTS}"
MODEL="${MODEL:-$WS/SUTA-LANGUES/Spark-TTS-0.5B}"
PORT="${PORT:-7860}"
LOG="${LOG:-$WS/suta-langues.log}"

echo "--- controles prealables ---"
[ -x "$VENV/bin/python" ] || { echo "ECHEC : venv absent ($VENV)"; exit 1; }
[ -f "$APP/webui.py" ]    || { echo "ECHEC : webui.py absent ($APP)"; exit 1; }
[ -d "$MODEL" ]           || { echo "ECHEC : modele absent ($MODEL)"; exit 1; }
nvidia-smi || { echo "ECHEC : pas de GPU visible"; exit 1; }
"$VENV/bin/pip" check || echo "ATTENTION : conflits pip (voir ci-dessus)"

echo
echo "--- versions epinglees attendues ---"
"$VENV/bin/pip" list 2>/dev/null | grep -Ei '^(gradio|gradio-client|pydantic) ' || true
echo "(attendu : gradio 5.18.0 / gradio-client 1.7.2 / pydantic 2.10.6)"

if ss -ltn 2>/dev/null | grep -q ":$PORT "; then
  echo "ATTENTION : le port $PORT est deja ecoute. Processus :"
  ss -ltnp 2>/dev/null | grep ":$PORT " || true
  exit 1
fi

echo
echo "--- lancement (detache, survit a la fermeture du terminal) ---"
cd "$APP"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
nohup python webui.py \
  --model_dir "$MODEL" \
  --device 0 \
  --server_name 0.0.0.0 \
  --server_port "$PORT" \
  >> "$LOG" 2>&1 &
PID=$!
echo "PID $PID — journal : $LOG"

echo "--- attente de lecoute sur 0.0.0.0:$PORT (90 s max) ---"
for i in $(seq 1 90); do
  if ss -ltn 2>/dev/null | grep -q ":$PORT "; then
    echo "OK : Spark-TTS ecoute sur 0.0.0.0:$PORT"
    ss -ltn | grep ":$PORT "
    echo
    echo "Ouvrir lURL HTTP du port $PORT depuis le bouton Connect du pod RunPod."
    echo "Verifier dans RunPod que le port $PORT est bien expose en HTTP."
    exit 0
  fi
  sleep 1
done

echo "ECHEC : rien necoute apres 90 s. 40 dernieres lignes du journal :"
tail -40 "$LOG"
exit 1
