#!/usr/bin/env bash
# Entraînement de la voix native de SUTA avec Piper, sur un pod GPU.
#
# CE QUE FAIT CE SCRIPT
#   point de reprise français → affinage sur nos enregistrements → voix .onnx
#
# POURQUOI UN AFFINAGE ET NON UN ENTRAÎNEMENT DEPUIS ZÉRO
#   Vingt minutes de parole ne suffisent pas à apprendre le français. Elles
#   suffisent à déplacer une voix française existante vers la nôtre. On part
#   donc de `siwis` : mono-locuteur, studio, 22 050 Hz — la même forme que nos
#   enregistrements. Les deux autres points de reprise français disponibles
#   (`mls`, `upmc`) sont multi-locuteurs : ils diluent l'identité qu'on cherche
#   justement à capter.
#
# AVANT DE LANCER
#   Le corpus doit être passé par outils/preparer_corpus_voix.py SANS bloquant.
#   Ce script ne revérifie rien : il entraîne ce qu'on lui donne.
#
# USAGE
#   ./outils/entrainer_piper.sh <dossier-dataset> [dossier-travail]

set -euo pipefail

DATASET="${1:?usage: $0 <dossier-dataset> [dossier-travail]}"
TRAVAIL="${2:-$PWD/piper-travail}"
LANGUE="${LANGUE:-fr}"
FREQUENCE="${FREQUENCE:-22050}"
LOT="${LOT:-16}"          # 16 tient sur un GPU 16 Go ; monter si la mémoire suit
EPOQUES="${EPOQUES:-2000}" # affinage : quelques centaines suffisent souvent

# Mono-locuteur, studio, 22 050 Hz — relevé le 24/09/2026 dans le dépôt.
DEPOT_CKPT="rhasspy/piper-checkpoints"
CKPT_DISTANT="fr/fr_FR/siwis/medium/epoch=3304-step=2050940.ckpt"

echo "== 0. Contrôles =="
test -f "$DATASET/metadata.csv" || { echo "metadata.csv introuvable dans $DATASET" >&2; exit 2; }
test -d "$DATASET/wav"          || { echo "dossier wav/ introuvable dans $DATASET" >&2; exit 2; }
PAIRES=$(wc -l < "$DATASET/metadata.csv")
echo "   $PAIRES paires audio/texte"
command -v nvidia-smi >/dev/null && nvidia-smi --query-gpu=name,memory.total --format=csv,noheader || echo "   (pas de GPU détecté — l'entraînement sera inutilisable)"

echo "== 1. Dépendances =="
# L'image recommandée par Piper est nvcr.io/nvidia/pytorch:22.03-py3.
python3 -m pip install --quiet --upgrade piper-tts piper-train huggingface_hub || {
  echo "Installation par pip échouée — cloner rhasspy/piper et installer src/python/" >&2
  exit 2
}

echo "== 2. Point de reprise français =="
mkdir -p "$TRAVAIL"
CKPT_LOCAL=$(python3 - "$DEPOT_CKPT" "$CKPT_DISTANT" "$TRAVAIL" <<'PY'
import sys
from huggingface_hub import hf_hub_download
print(hf_hub_download(repo_id=sys.argv[1], repo_type="dataset",
                      filename=sys.argv[2], local_dir=sys.argv[3]))
PY
)
echo "   $CKPT_LOCAL"

echo "== 3. Préparation Piper =="
ENTRAINEMENT="$TRAVAIL/entrainement"
mkdir -p "$ENTRAINEMENT"
python3 -m piper_train.preprocess \
  --language "$LANGUE" \
  --input-dir "$DATASET" \
  --output-dir "$ENTRAINEMENT" \
  --dataset-format ljspeech \
  --single-speaker \
  --sample-rate "$FREQUENCE"

echo "== 4. Affinage =="
# --validation-split 0 et --num-test-examples 0 : sur 250 phrases, retirer un
# lot de validation coûte plus qu'il ne renseigne. On juge à l'oreille.
python3 -m piper_train \
  --dataset-dir "$ENTRAINEMENT" \
  --accelerator gpu \
  --devices 1 \
  --batch-size "$LOT" \
  --validation-split 0.0 \
  --num-test-examples 0 \
  --max_epochs "$EPOQUES" \
  --resume_from_checkpoint "$CKPT_LOCAL" \
  --checkpoint-epochs 25 \
  --precision 32

echo "== 5. Export =="
DERNIER=$(ls -t "$ENTRAINEMENT"/lightning_logs/*/checkpoints/*.ckpt 2>/dev/null | head -1)
test -n "$DERNIER" || { echo "Aucun point de contrôle produit" >&2; exit 2; }
mkdir -p "$TRAVAIL/voix"
python3 -m piper_train.export_onnx "$DERNIER" "$TRAVAIL/voix/suta-fr.onnx"
cp "$ENTRAINEMENT/config.json" "$TRAVAIL/voix/suta-fr.onnx.json"

echo "== 6. Essai =="
echo "Bonjour, je suis SUTA. À Nambékaha, la fibre n'est pas encore arrivée." \
  | piper --model "$TRAVAIL/voix/suta-fr.onnx" --output_file "$TRAVAIL/voix/essai.wav" \
  && echo "   $TRAVAIL/voix/essai.wav"

echo
echo "Voix : $TRAVAIL/voix/suta-fr.onnx ($(du -h "$TRAVAIL/voix/suta-fr.onnx" | cut -f1))"
echo "Écoutez essai.wav AVANT d'aller plus loin : les toponymes sont le juge."
echo "Trop métallique ou haché → plus d'époques. Bon dès 300 → arrêter là,"
echo "un affinage trop long finit par réciter le corpus au lieu de parler."
