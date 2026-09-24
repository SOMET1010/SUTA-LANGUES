# Passation — SUTA-LANGUES / MALIBA

**Dernière mise à jour : 24/09/2026** · Dépôt : `somet1010/suta-langues` ·
Branche de travail : `claude/zen-euler-sigjls` · Responsable : Patrick (psomet@gmail.com)

Ce document est autoportant : un agent qui le lit doit pouvoir reprendre sans
relire l'historique de conversation. Il couvre **deux chantiers distincts**.

---

## 0. Règles de travail imposées par Patrick

Non négociables, elles priment sur toute initiative :

1. **Ne rien présumer.** La source de vérité est cette passation et les
   instructions de Patrick. Information manquante → écrire « À DÉFINIR » et
   **poser la question**, ne pas inventer.
2. **Plan clair avant de coder, puis attendre validation.** Aucun changement
   d'architecture sans prévenir.
3. **Un projet = une session + un dépôt dédié.** Ne rien mélanger.
4. **Git** : branche dédiée (`claude/zen-euler-sigjls`), commits clairs et
   fréquents, push régulier. **Aucune pull request sans demande explicite.**
5. **Réponses en français**, concises : ce qui a été fait, ce qui marche ou non,
   la prochaine étape. Tout arbitrage (design, priorité, budget) revient à Patrick.
6. **Lovable uniquement pour prévisualiser une interface, sur demande explicite.**
   Jamais pour le reste (coûteux). La preview live passe par un déploiement auto
   branché sur GitHub.

---

## 1. Ce qu'est le projet

**SUTA-LANGUES** : service indépendant de transcription (ASR) des langues
ivoiriennes, appelé par SUTA via `LABO_ASR_ENDPOINT`, sans modifier le code de SUTA.

- Contrat : `POST /v1/transcrire` (audio base64 + `lang`) → `{texte, traduction, lang, modele, duree_ms}`
- `GET /v1/langues` → 24 langues ivoiriennes, vérifiées dans `lang_ids.py`
  d'omnilingual-asr 0.2.0 (revérifié le 11/09/2026). **Leur présence dans le
  modèle est confirmée, leur qualité reste à mesurer avec des locuteurs.**
- Modèle ASR par défaut : `omniASR_CTC_300M_v2` (~1,3 Gio, ~2 Gio de VRAM)
- Protection : `LANGUES_API_KEY` → en-tête `Authorization: Bearer`. Côté SUTA
  c'est `LABO_ASR_KEY`, même valeur. **Clé obligatoire en production**, transmise
  par coffre à secrets, jamais par messagerie.
- Code : `src/suta_langues/` (main, backend, languages, static) + `maliba_service.py`

**MALIBA** : le volet synthèse vocale (TTS), déployé sur RunPod — voir chantier A.

---

## 2. Chantier A — Remise en service RunPod (EN COURS, bloqué sur action humaine)

### Situation

Le pod GPU qui faisait tourner MALIBA / Spark-TTS ne redémarre plus : plus aucune
RTX 3090 en stock chez RunPod. **Les données sont intactes mais prisonnières d'un
pod arrêté.** L'objectif est de les sauvegarder vers un Network Volume, puis de
relancer le service sur un GPU disponible.

### Inventaire vérifié dans l'UI RunPod (15/09/2026)

| Pod | ID | Région | GPU | Prix/h | `/workspace` |
|---|---|---|---|---|---|
| suta-langues-a40-migration | `evnhxolsqj8oz3` | EU-CZ-1 | 1× RTX 3090 | 0,50 $ | volume de pod 50 Go — **source des données** |
| suta-langues-a40 | `r9pmr12s7bbpc0` | EU-CZ-1 | 1× RTX 3090 | 0,50 $ | volume de pod 50 Go — doublon, **contenu inconnu** |
| suta-langues-test | `sgcli9bs7s9v5h` | EU-RO-1 | 1× RTX 4090 | 0,74 $ | **Network Volume `vn82f9ix44`** — destination |

Les trois sont **arrêtés** (`EXITED`), image `runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404`,
disque conteneur 60 Go. Les pods « a40 » n'ont **pas** de GPU A40 : c'est une RTX 3090,
le nom est trompeur.

**Network Volume** : `suta-langues-test_volume`, ID `vn82f9ix44`, 50 Go, **EU-RO-1**,
3,50 $/mois. Accessible en **API S3** : endpoint `https://s3api-eu-ro-1.runpod.io`,
bucket `vn82f9ix44`, région `eu-ro-1`.

### Contenu attendu de `/workspace` (source)

```
/workspace/SUTA-LANGUES/                  dont Spark-TTS-0.5B/  <- poids du modèle
/workspace/Spark-TTS/                     clone officiel, contient webui.py
/workspace/maliba-venv/                   environnement Python fonctionnel
/workspace/maliba-test.wav                WAV de test déjà généré avec succès
/workspace/suta-langues.log
```

Versions épinglées qui fonctionnaient, **à préserver** : `gradio==5.18.0`,
`gradio-client==1.7.2`, `pydantic==2.10.6`. `pip check` était propre.

Commande qui démarrait correctement l'interface :

```bash
cd /workspace/Spark-TTS && source /workspace/maliba-venv/bin/activate
python webui.py --model_dir /workspace/SUTA-LANGUES/Spark-TTS-0.5B \
  --device 0 --server_name 0.0.0.0 --server_port 7860
```

### Les trois contraintes qui déterminent le plan

1. **Le pod source démarre en CPU.** L'UI propose `Start → Start Pod using CPUs`.
   Sans GPU disponible, c'est **la seule voie d'accès aux données**. Suffisant pour
   inventorier et copier. En CPU, `nvidia-smi` ne répond pas et
   `torch.cuda.is_available()` est `False` : normal, sans effet sur la sauvegarde.
2. **Source en EU-CZ-1, volume en EU-RO-1.** Un Network Volume ne s'attache qu'à un
   pod de sa région, et seulement **à la création du pod**. Le pod source ne pourra
   donc **jamais** monter ce volume. → passer par l'**API S3** du volume, ce qui
   supprime aussi le besoin d'un second pod allumé.
3. **Aucun pod à créer.** `suta-langues-test` monte **déjà** le Network Volume :
   c'est lui la destination. Mais plus aucune RTX 4090 en EU-RO-1 → il faut
   **changer son type de GPU**.

### GPU de destination — décision

Spark-TTS 0,5 B en inférence tient sous 8 Go de VRAM. Disponibles en EU-RO-1 :

| Rang | GPU | VRAM | Prix/h | Stock |
|---|---|---|---|---|
| 1 | **RTX 2000 Ada** | 16 Go | **0,24 $** | faible |
| 2 | L4 | 24 Go | 0,49 $ | faible |
| 3 | RTX PRO 4000 | 24 Go | 0,57 $ | faible |
| secours | RTX PRO 6000 | 96 Go | 2,09 $ | **élevé** — seul stock fiable, à arrêter dès le test fait |

À éviter : A100 (1,59 $), MI300X (2,39 $), H100/H200 — aucun bénéfice ici.

### Outils livrés — dossier `runpod/`

Tous testés syntaxiquement (`bash -n`). **Aucun ne supprime quoi que ce soit.**

| Script | Où l'exécuter | Rôle |
|---|---|---|
| `01_inventaire.sh` | pod source (CPU) | **lecture seule** : tailles, présence des 6 éléments critiques, `pip check`, manifeste fichier par fichier, SHA256 des fichiers critiques |
| `02_copie.sh` | pod destination | `rsync` en *pull*, sans `--delete`, `--dry-run` disponible, relançable |
| `02b_copie_runpodctl.sh` | pod source | secours pair-à-pair si pas de SSH entre pods |
| `05_s3_sauvegarde.sh` | pod source (CPU) | **voie retenue** : archives `tar.gz` streamées vers `s3://vn82f9ix44/_sauvegarde/` |
| `06_s3_restauration.sh` | pod destination | déballe les archives, **n'écrase jamais** un dossier existant |
| `03_verification.sh` | pod destination | **sort en erreur** si un élément manque ou est vide ; diff avec le manifeste source |
| `04_relance_sparktts.sh` | pod destination | contrôle venv + modèle + `nvidia-smi` + `pip check`, lance `webui.py` en détaché, attend l'écoute sur `0.0.0.0:7860` |

Le runbook détaillé est dans **`runpod/README.md`** — le lire avant d'agir.

Le venv est restauré **au même chemin** `/workspace/maliba-venv` : ses chemins
absolus restent valides, **aucune réinstallation nécessaire**.

### Règle de choix de la voie de copie

Le Network Volume fait 50 Go, et la voie S3 dépose les archives **sur le volume**
puis les déballe **sur le volume** : il faut la place des deux.

- `/workspace` source **≤ ~22 Go** → voie S3 (`05` puis `06`), un seul pod allumé
- `/workspace` source **> ~22 Go** → `02_copie.sh` (rsync direct, les deux pods en
  CPU), aucune archive intermédiaire, donc 1× l'espace

**L'inventaire tranche. Ne pas choisir avant de l'avoir.**

### Garde-fous — à ne jamais enfreindre

- Jamais de `rm -rf` ni d'aucune suppression dans `/workspace`.
- **Jamais de `Terminate`** sur un pod avant vérification verte **et** accord
  explicite de Patrick. Terminer le pod source = perte définitive des données.
- Ne pas retélécharger le modèle si les poids existent.
- Ne pas réinstaller les dépendances si `maliba-venv` fonctionne.
- Avant toute action destructive : afficher exactement ce qui sera supprimé et
  attendre validation.

### PROCHAINE ÉTAPE — une seule

Patrick doit faire : pod `evnhxolsqj8oz3` → **Start → Start Pod using CPUs** →
Web Terminal, puis exécuter **une commande à la fois** et transmettre chaque sortie :

```bash
ls -lah /workspace          # 1. les 4 éléments critiques sont-ils là ?
df -h /workspace            # 2. remplissage réel
du -sh /workspace/* | sort -h   # 3. poids par dossier -> décide S3 vs rsync
```

Puis seulement, selon la volumétrie, `01_inventaire.sh` et la voie de copie retenue.
Les commandes complètes sont dans `runpod/README.md`.

### Points ouverts — À DÉFINIR

1. Le Network Volume `vn82f9ix44` est-il vide, ou contient-il déjà des données ?
   (Réponse rapide : démarrer `suta-langues-test` en CPU et faire
   `ls -lah /workspace && df -h /workspace`, quelques centimes.)
2. Que contient `suta-langues-a40` (`r9pmr12s7bbpc0`) ? À inventorier avant
   d'envisager quoi que ce soit le concernant.
3. La clé S3 RunPod (Settings → S3 API Keys) est-elle créée ?
4. Budget horaire accepté pour le GPU de destination.

### Coût du statu quo

Trois volumes de 50 Go facturés en permanence, pods arrêtés compris :
~0,014 $/h × 2 volumes de pod ≈ **20 $/mois**, plus 3,50 $/mois de Network Volume,
soit **~24 $/mois**. C'est ce que la migration doit permettre d'arrêter — mais
seulement après vérification verte et accord explicite.

---

## 3. Chantier B — Ressources dioula (TERMINÉ, recherche)

Fiche complète : **`docs/ressources-dioula.md`**. Résumé :

- **Meilleure ressource : Koumankan4Dyula** (UVCI, Côte d'Ivoire) — ~15 h d'audio,
  10 929 enregistrements, transcription dioula + traduction fr + en, publié et
  doté d'un DOI. **Gated** : la demande d'accès est le geste le plus urgent, c'est
  le délai le plus long.
- **Piège** : les ressources dioula sont taguées `language:bm`, pas `dyu`.
- **Deux alertes pour le projet** :
  1. Le modèle déployé, `MALIBA-AI/bambara-tts`, est un finetune de Spark-TTS-0.5B
     **en bambara**, pas en dioula ivoirien.
  2. Sa licence est **CC-BY-NC-SA-4.0 — non commercial**. Si SUTA vise le
     commercial, c'est bloquant, et **à trancher avant d'investir du GPU**.
     → **décision attendue de Patrick.**

---

## 4. Limites de l'environnement d'exécution (à connaître)

Testé le 15/09/2026 depuis la session Claude Code cloud :

| Hôte | État |
|---|---|
| `api.runpod.io`, `rest.runpod.io`, `console.runpod.io` | **bloqués** (403 CONNECT) |
| `s3api-eu-ro-1.runpod.io`, `docs.runpod.io` | **bloqués** |
| `mcp.getrunpod.io` (MCP RunPod officiel) | **bloqué** |
| SSH sortant (port 22) | **bloqué** |
| `registry.npmjs.org`, GitHub, Hugging Face | accessibles |

**Conséquence : aucun agent de cette session cloud ne peut piloter RunPod.** Les
commandes passent par le Web Terminal du pod, exécutées par Patrick.

Le **MCP RunPod officiel** (`https://mcp.getrunpod.io/`) est la bonne solution mais
doit tourner **sur la machine de Patrick** :

```bash
npx @runpod/mcp-server@latest add        # installateur automatique
# ou
claude mcp add --transport http runpod -s user https://mcp.getrunpod.io/
# puis /mcp -> Sign in with RunPod
```

Il couvre le **plan de contrôle** RunPod (démarrer un pod, changer le GPU, exposer
un port, lister les disponibilités). **Rien ne garantit qu'il donne un shell dans
le pod** — à vérifier en lui demandant la liste de ses outils. Tant que ce n'est
pas constaté, les scripts passent par le Web Terminal.

---

## 5. Journal

| Date | Vérifié | Changé | Reste à faire |
|---|---|---|---|
| 15/09 | Accès RunPod depuis la session cloud : tout bloqué. Dépôt : aucune trace de la config RunPod/Spark-TTS. | Création du dossier `runpod/` : runbook + 7 scripts. | Inventaire sur le pod source. |
| 15/09 | Correction : le pod **peut** redémarrer en CPU. Source en EU-CZ-1, volume en EU-RO-1, volume accessible en S3. | Voie S3 retenue ; ajout de `05_` et `06_`. | Créer la clé S3. |
| 15/09 | Relevé complet du compte : 3 pods arrêtés, plus aucune RTX 3090 ni 4090 utile ; `suta-langues-test` monte déjà le volume. | Choix du GPU de destination ; règle S3 vs rsync. | Démarrer le pod source en CPU. |
| 21/09 | Ressources dioula relevées sur le Hub. `MALIBA-AI/bambara-tts` identifié comme le modèle déployé : bambara, licence NC. | — | Demander l'accès à Koumankan ; trancher la licence NC. |
| 24/09 | — | Création de `PASSATION.md` et `docs/ressources-dioula.md`. | **Chantier A : `ls -lah /workspace` sur `evnhxolsqj8oz3` démarré en CPU.** |

---

## 6. Démarrage rapide pour l'agent qui reprend

1. Lire ce document, puis `runpod/README.md`.
2. Ne rien exécuter sur RunPod soi-même : c'est bloqué. Donner à Patrick **une
   commande à la fois**, attendre sa sortie, puis décider.
3. Le chantier A est **bloqué sur une action humaine** : le démarrage CPU du pod
   `evnhxolsqj8oz3`. Tant qu'elle n'est pas faite, rien d'autre n'avance côté infra.
4. Deux décisions appartiennent à Patrick et ne doivent pas être prises à sa place :
   la **licence NC** du modèle MALIBA, et le **budget GPU**.
5. Commits sur `claude/zen-euler-sigjls`, messages clairs, push régulier,
   **aucune pull request sans demande**.
