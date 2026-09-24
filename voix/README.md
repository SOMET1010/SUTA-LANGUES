# Voix native de SUTA

La chaîne, de la lecture à la voix :

```
script-enregistrement-fr.txt   254 phrases à lire
        ↓  une personne, une pièce silencieuse, deux à trois séances
brut/0001.wav … 0254.wav       + 0000.wav (30 s de silence de la pièce)
        ↓  outils/preparer_corpus_voix.py   — vérifie, ne convertit rien
dataset/metadata.csv + wav/    format attendu par Piper
        ↓  outils/entrainer_piper.sh        — sur un pod GPU, ~20 $
voix/suta-fr.onnx              20 à 60 Mo, tourne sur processeur
```

## Pourquoi Piper et pas Azure

Une voix Piper **s'embarque dans l'APK** : 20 à 60 Mo, pas de réseau, pas
d'abonnement. C'est ce dont PASS a besoin, et ce qu'Azure ne permettra jamais —
son hébergement de voix custom coûte environ 2 900 $ par mois en continu, et
exige une connexion à chaque phrase.

## Les deux commandes

```bash
# 1. Vérifier les enregistrements et construire le jeu de données
python3 outils/preparer_corpus_voix.py \
    --audio voix/brut \
    --script voix/script-enregistrement-fr.txt \
    --sortie voix/dataset

# 2. Entraîner, sur le pod
./outils/entrainer_piper.sh voix/dataset
```

La première refuse de construire s'il reste un problème bloquant. C'est
volontaire : un décalage d'un fichier entre l'audio et le texte ne se voit
qu'après l'entraînement, et coûte alors la séance entière.

## Ce que la vérification regarde

| Contrôle | Ce qu'il attrape |
|---|---|
| Correspondance audio ↔ texte | une phrase sautée, un fichier en trop — le défaut qui ruine tout |
| Fréquence, canaux, bits | un réglage changé en cours de séance |
| Durée | phrase tronquée, ou deux phrases dans un fichier |
| Saturation | micro trop près, niveau d'entrée trop haut |
| Silences de tête et de queue | montage bâclé |
| Régularité du niveau | **le micro a été déplacé entre deux prises** |
| Bruit de fond (`0000.wav`) | la pièce n'était pas assez silencieuse |

## Enregistrer les langues locales

Même chaîne, même outils. Deux différences :

- **Le script doit être écrit par un locuteur natif**, pas traduit du français.
  Le meilleur traducteur baoulé plafonne à chrF++ 18,2 : on ferait lire des
  phrases fausses, et la voix apprendrait les fautes.
- **La même personne doit enregistrer les trois langues**, sinon SUTA change de
  voix en changeant de langue.

Les toponymes, eux, ne se traduisent pas : Nambékaha reste Nambékaha.
