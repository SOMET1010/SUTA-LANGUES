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
# CE QUI A ÉTÉ VÉRIFIÉ EN EXÉCUTANT, LE 26/09/2026
#   Tout ce script avait été écrit sans pouvoir être lancé. Une répétition sur
#   CPU, avec le corpus réel, a montré qu'il aurait échoué sur le pod — après
#   facturation. Quatre erreurs corrigées, toutes constatées :
#
#   1. `piper-train` N'EXISTE PAS sur PyPI. Le bon paquet est `piper-tts`, et
#      l'entraînement est une option : `pip install "piper-tts[train]"`.
#   2. La CLI a changé. `python3 -m piper_train --dataset-dir …` appartient à
#      Piper 0.x ; la 1.8 expose une CLI Lightning : `python3 -m piper.train
#      fit --data.* --model.* --trainer.*`. Il n'y a plus d'étape `preprocess`
#      séparée : le module de données phonémise lui-même.
#   3. La roue `piper-tts[train]` livre `monotonic_align` SANS son extension
#      compilée, et sans même le `core.pyx` qui permettrait de la compiler.
#      L'entraînement plante à la première étape. Étape 2 ci-dessous : on va
#      chercher la source sur GitHub et on compile.
#   4. La voix eSpeak est `fr`. Ni `fr-FR`, ni `fr-fr`, qui n'existent pas —
#      eSpeak ne connaît que `fr`, `fr-BE` et `fr-CH`. (Ni `fr-CI`, du reste :
#      cette locale n'existe pas davantage ici qu'ailleurs.)
#
#   Vérifié aussi : la table de phonèmes écrite par la 1.8 coïncide exactement
#   avec celle de `siwis` sur ses identifiants — les embeddings s'alignent,
#   l'affinage part donc du bon endroit.
#
#   RESTE NON VÉRIFIÉ : que les poids de `siwis`, entraînés avec l'ancien
#   `piper_train`, se chargent tels quels dans le modèle de la 1.8.
#   Impossible à éprouver hors d'un pod : huggingface.co est bloqué en
#   téléchargement depuis les sessions d'agent, et le point de reprise fait
#   845 Mo. C'est le premier point à contrôler sur le pod, à l'étape 4.
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
NOM_VOIX="${NOM_VOIX:-suta-fr}"
VOIX_ESPEAK="${VOIX_ESPEAK:-fr}"   # vérifié : `fr-FR` n'existe pas dans eSpeak
FREQUENCE="${FREQUENCE:-22050}"
LOT="${LOT:-16}"           # 16 tient sur un GPU 16 Go ; monter si la mémoire suit
EPOQUES="${EPOQUES:-2000}" # affinage : quelques centaines suffisent souvent

# Mono-locuteur, studio, 22 050 Hz, jeu de données CC-BY 4.0 — relevé le
# 26/09/2026 dans la fiche du dépôt.
DEPOT_CKPT="rhasspy/piper-checkpoints"
CKPT_DISTANT="fr/fr_FR/siwis/medium/epoch=3304-step=2050940.ckpt"

mkdir -p "$TRAVAIL"

echo "== 0. Contrôles =="
test -f "$DATASET/metadata.csv" || { echo "metadata.csv introuvable dans $DATASET" >&2; exit 2; }
test -d "$DATASET/wav"          || { echo "dossier wav/ introuvable dans $DATASET" >&2; exit 2; }
PAIRES=$(wc -l < "$DATASET/metadata.csv")
echo "   $PAIRES paires audio/texte"
command -v nvidia-smi >/dev/null \
  && nvidia-smi --query-gpu=name,memory.total --format=csv,noheader \
  || echo "   (pas de GPU détecté — mesuré : ~7 s par étape sur 4 cœurs CPU, donc inutilisable)"

echo "== 1. Dépendances =="
python3 -m pip install --quiet --upgrade "piper-tts[train]" huggingface_hub cython || {
  echo "Installation par pip échouée." >&2
  exit 3
}

echo "== 2. Réparation de monotonic_align =="
# La roue livre le paquet amputé de son extension Cython ET de sa source. Sans
# cette étape, l'entraînement s'arrête net à la première étape sur :
#   ModuleNotFoundError: No module named 'piper.train.vits.monotonic_align.monotonic_align'
MA_DIR="$(python3 -c 'import piper.train.vits.monotonic_align as m, pathlib; print(pathlib.Path(m.__file__).parent)')"
if python3 -c 'from piper.train.vits.monotonic_align import maximum_path' 2>/dev/null; then
  echo "   déjà fonctionnel"
else
  BUILD="$TRAVAIL/monotonic_align-build"
  rm -rf "$BUILD"; mkdir -p "$BUILD"
  curl -sSL -o "$BUILD/core.pyx" \
    "https://raw.githubusercontent.com/OHF-Voice/piper1-gpl/main/src/piper/train/vits/monotonic_align/core.pyx"
  cat > "$BUILD/setup.py" <<'PY'
from distutils.core import setup
import numpy
from Cython.Build import cythonize
setup(name="core", ext_modules=cythonize("core.pyx"), include_dirs=[numpy.get_include()])
PY
  # On compile avec un chemin RELATIF : un chemin absolu donné à cythonize
  # devient le nom du module, et la bibliothèque part dans une arborescence
  # fantôme au lieu du paquet.
  (cd "$BUILD" && python3 setup.py build_ext --inplace >/dev/null)
  mkdir -p "$MA_DIR/monotonic_align"
  touch "$MA_DIR/monotonic_align/__init__.py"
  cp "$BUILD"/core*.so "$MA_DIR/monotonic_align/"
  python3 -c 'from piper.train.vits.monotonic_align import maximum_path' \
    || { echo "monotonic_align toujours cassé" >&2; exit 3; }
  echo "   compilé et installé dans $MA_DIR/monotonic_align/"
fi

echo "== 3. Point de reprise français =="
CKPT_LOCAL="$TRAVAIL/$(basename "$CKPT_DISTANT")"
if [ -f "$CKPT_LOCAL" ]; then
  echo "   déjà présent : $CKPT_LOCAL"
else
  python3 - <<PY
from huggingface_hub import hf_hub_download
import shutil
chemin = hf_hub_download(repo_id="$DEPOT_CKPT", filename="$CKPT_DISTANT", repo_type="dataset")
shutil.copy2(chemin, "$CKPT_LOCAL")
print("   téléchargé :", "$CKPT_LOCAL")
PY
fi

echo "== 4. Affinage =="
# --data.config_path est une SORTIE : l'entraîneur y écrit la configuration de
# la voix (table de phonèmes, fréquence). Ce n'est pas la config du point de
# reprise.
#
# Si cette étape échoue sur des clés de state_dict inattendues, c'est le point
# resté non vérifié en tête de fichier : les poids de `siwis` viennent de
# l'ancien entraîneur. Dans ce cas, relancer SANS --ckpt_path donne un
# entraînement depuis zéro — inutile sur douze minutes de parole — donc mieux
# vaut s'arrêter et le signaler.
#
# Avertissement bénin observé : « Could not load MOS predictor 'utmos' (403) ».
# C'est une métrique de confort, désactivée d'elle-même. Rien à corriger.
python3 -m piper.train fit \
  --data.csv_path "$DATASET/metadata.csv" \
  --data.audio_dir "$DATASET/wav" \
  --data.cache_dir "$TRAVAIL/cache" \
  --data.config_path "$TRAVAIL/$NOM_VOIX/config.json" \
  --data.espeak_voice "$VOIX_ESPEAK" \
  --data.voice_name "$NOM_VOIX" \
  --data.batch_size "$LOT" \
  --model.sample_rate "$FREQUENCE" \
  --trainer.accelerator gpu \
  --trainer.devices 1 \
  --trainer.precision 32 \
  --trainer.max_epochs "$EPOQUES" \
  --trainer.default_root_dir "$TRAVAIL/$NOM_VOIX" \
  --ckpt_path "$CKPT_LOCAL"

echo "== 5. Export ONNX =="
DERNIER=$(find "$TRAVAIL/$NOM_VOIX" -name '*.ckpt' -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)
test -n "$DERNIER" || { echo "aucun point de reprise produit" >&2; exit 4; }
echo "   depuis $DERNIER"
python3 -m piper.train.export_onnx "$DERNIER" "$TRAVAIL/voix/$NOM_VOIX.onnx"
cp "$TRAVAIL/$NOM_VOIX/config.json" "$TRAVAIL/voix/$NOM_VOIX.onnx.json"

echo "== 6. Épreuve à l'oreille =="
# Les six noms qui mettent en défaut une voix entraînée sur du français
# hexagonal. C'est sur eux que se juge le résultat, pas sur « bonjour ».
echo "Korhogo. Yamoussoukro. Nambékaha. N'Guessankro. Bogodougou. Sinématiali." \
  | python3 -m piper --model "$TRAVAIL/voix/$NOM_VOIX.onnx" \
      --output-file "$TRAVAIL/voix/epreuve-toponymes.wav"
echo
echo "Voix : $TRAVAIL/voix/$NOM_VOIX.onnx"
echo "Épreuve : $TRAVAIL/voix/epreuve-toponymes.wav — à écouter avant toute conclusion."
