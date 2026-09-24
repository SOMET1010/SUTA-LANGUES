# Ressources dioula (dyu) — état de l'art au 21/09/2026

Relevé fait sur le Hugging Face Hub via le connecteur HF, pas de mémoire.
Chaque ligne a été vérifiée sur la fiche du dépôt.

## Le piège à connaître avant de chercher

**Les ressources dioula sont taguées `language:bm` (bambara), pas `dyu`.**
Koumankan lui-même, pourtant produit en Côte d'Ivoire, est tagué `bm`. Un filtre
`language:dyu` sur le Hub ne renvoie que des corpus massifs génériques
(FLORES+, FineWeb-2, SIB-200, Glot500). Chercher `bambara` **et** `dioula`,
jamais `dyu` seul.

Raison linguistique : dioula, bambara et malinké sont sur le continuum manding et
largement intelligibles entre eux. Les jeux de données les mélangent souvent.

## La meilleure ressource : Koumankan4Dyula

| | |
|---|---|
| Dépôt audio | https://huggingface.co/datasets/uvci/koumankan4dyula |
| Dépôt texte (MT) | https://huggingface.co/datasets/uvci/Koumankan_mt_dyu_fr |
| Producteur | Université Virtuelle de Côte d'Ivoire (UVCI) |
| Financement | IDRC + SIDA, via l'African Center for Technology Studies |
| Papier | https://openreview.net/pdf?id=swtk4Djrz2 |
| DOI | `10.57967/hf/9420` (audio), `10.57967/hf/6642` (texte) |
| Volume audio | ~15 h, 10 929 enregistrements |
| Contenu | audio + transcription dioula + traduction française + anglaise |
| Paires MT | 10 929 (train 8 065 / valid 1 471 / test 1 393) |
| Popularité | 4,0 K et 4,4 K téléchargements |
| Accès | **gated** — demande d'accès obligatoire, prévoir du délai |
| Locuteurs | Burkina Faso majoritairement, et Côte d'Ivoire |

C'est la seule ressource dioula à la fois **volumineuse, documentée, publiée et
ivoirienne**. Point de départ par défaut pour tout travail sérieux sur le dioula.

## Le reste du paysage

| Usage | Ressource | Volume / nature | Licence | Accès |
|---|---|---|---|---|
| Plus gros audio | [madoss/merged-bambara-dioula-dataset](https://huggingface.co/datasets/madoss/merged-bambara-dioula-dataset) | **85 000 lignes**, audio 16 kHz + transcription + fr, ~13,8 Go (train 70,1 K / test 9,9 K / valid 5,0 K) | **non déclarée** | libre |
| TTS dioula prêt | [facebook/mms-tts-dyu](https://huggingface.co/facebook/mms-tts-dyu) | VITS 36,3 M, 8,3 K téléchargements | **CC-BY-NC-4.0** | libre |
| ASR dioula | [ikone22/mms-1b-dyula](https://huggingface.co/ikone22/mms-1b-dyula) | wav2vec2 964,7 M finetuné | non déclarée | libre |
| MT fr↔dioula | [Findora/hf_fr_dioula_full](https://huggingface.co/datasets/Findora/hf_fr_dioula_full) | 25 600 paires (20,5 K / 2,6 K / 2,6 K) | **Apache-2.0** | libre |
| Évaluation ASR+TTS | [UBC-NLP/SimbaBench_dataset](https://huggingface.co/datasets/UBC-NLP/SimbaBench_dataset) | benchmark multilingue incluant `dyu` | — | libre |
| Audio (à explorer) | [goaicorp/goai-dioula-speech](https://huggingface.co/datasets/goaicorp/goai-dioula-speech) | 10 K–100 K lignes | non déclarée | **gated manuel** |
| Modèles de langue | [goldfish-models/dyu_latn_full](https://huggingface.co/goldfish-models/dyu_latn_full) | petit LM monolingue dyu | — | libre |

## Point critique pour SUTA : le modèle MALIBA est en bambara

[`MALIBA-AI/bambara-tts`](https://huggingface.co/MALIBA-AI/bambara-tts) — le modèle
déployé sur RunPod — est un **finetune de `SparkAudio/Spark-TTS-0.5B` entraîné en
bambara** (`language:bm`), par le collectif malien MALIBA-AI.

Deux conséquences :

1. **Ce n'est pas du dioula ivoirien.** L'intelligibilité manding fait que ça
   « passe » à peu près, mais l'écart s'entendra auprès de locuteurs ivoiriens.
   Une adaptation sur données dioula (Koumankan) est nécessaire pour un rendu juste.
2. **Licence CC-BY-NC-SA-4.0 = non commercial.** Si SUTA a une visée commerciale,
   c'est bloquant, et ça doit être tranché **avant** d'investir du GPU dans un
   finetune qui en hériterait. → décision à prendre par Patrick.

Autres modèles MALIBA-AI relevés : `bambara-asr-v1/v2/v3` (LoRA sur Whisper
large-v2/v3), `bambara-embeddings` (fastText), `bambara-tts-gguf`,
datasets `bambara-asr-benchmark` et `bambara-mt-dataset`, Space
`bambara-asr-leaderboard`.

## Trajectoire recommandée pour le TTS dioula

```
SparkAudio/Spark-TTS-0.5B          (socle, licence à vérifier)
        v
MALIBA-AI/bambara-tts              (état actuel du déploiement — bambara, NC)
        v
adaptation dioula sur Koumankan4Dyula (~15 h) + merged-bambara-dioula (85 K lignes)
```

Étape bloquante en tête de file : **demander l'accès aux deux dépôts Koumankan**,
c'est le délai le plus long.

## Ce qui n'a PAS été vérifié

- Le contenu réel des jeux *gated* (Koumankan, goai-dioula-speech) : accès non demandé.
- La licence de `madoss/merged-bambara-dioula-dataset` et de `ikone22/mms-1b-dyula` :
  aucune déclarée sur le dépôt. À contrôler avant tout usage en production.
- La qualité perçue de chaque modèle : aucun test d'écoute mené.
- Les 24 langues ivoiriennes du service ASR (`src/suta_langues/languages.py`) :
  leur présence dans omnilingual-asr est confirmée, **leur qualité ne l'est pas**
  (voir README, à mesurer avec des locuteurs).
