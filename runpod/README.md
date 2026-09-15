# Remise en service SUTA-LANGUES / MALIBA sur RunPod

Ordre imposé : **inventaire → sauvegarde → vérification → redéploiement**.
Rien n'est supprimé tant que `03_verification.sh` n'est pas passé au vert.

## 0. Ce que je peux et ne peux pas faire depuis cette session

Vérifié le 2026-09-15 depuis le conteneur d'exécution :

| Accès | État |
|---|---|
| `api.runpod.io` / `rest.runpod.io` | **bloqué** (403 CONNECT, politique réseau de l'environnement) |
| `docs.runpod.io`, `runpod.io` | **bloqué** |
| SSH sortant (port 22) | **bloqué** |
| Clé API RunPod dans l'environnement | **absente** |

Conséquence : je **ne peux pas** piloter RunPod moi-même (ni lister les pods, ni
en démarrer un, ni exécuter une commande dedans). Les scripts de ce dossier sont
faits pour être collés dans le **terminal web du pod** ; tu me renvoies la sortie
et je décide de la suite.

## 1. Contrainte structurante à connaître avant de cliquer

Un Network Volume RunPod s'attache **à la création du pod** et se monte sur
`/workspace`. L'ancien pod a son **propre volume disque** sur `/workspace` : il ne
peut donc pas monter le Network Volume en plus au même endroit. La copie se fait
donc **de pod à pod**, pas par « rebranchement » du volume.

Deux chemins possibles, par ordre de préférence :

- **A — l'ancien pod redémarre** (autre GPU disponible dans son datacenter) :
  on le démarre, on inventorie, on tire les données vers le nouveau pod.
- **B — l'ancien pod ne redémarre pas du tout** : les données sont bloquées
  dans son datacenter. Seul recours : support RunPod. **Ne pas terminer le pod**,
  ce serait la perte définitive.

Point à confirmer dans l'UI (je ne peux pas le vérifier) : RunPod permet d'éditer
un pod **arrêté** pour changer de type de GPU, mais **dans le même datacenter**.
Un pod GPU ne se convertit pas en pod CPU.

## 2. Informations manquantes — À DÉFINIR

Je ne les invente pas, il me les faut avant d'aller plus loin :

1. **Datacenter de l'ancien pod `suta-langues-a40-migration`** — visible sur la carte du pod.
   S'il n'est pas dans `EU-RO-1`, la copie est inter-région (plus lente, mais faisable).
2. **L'ancien pod existe-t-il toujours** (arrêté, pas terminé) ?
3. **Volumétrie réelle de `/workspace`** — donnée par l'étape 3 ci-dessous.
   Le Network Volume fait 50 Go ; un venv avec torch + le modèle peut approcher 15-20 Go.
4. **Budget/heure acceptable** pour le nouveau GPU.
5. Le Network Volume `suta-langues-test_volume` (`vn82f9ix44`) est-il **vide** ou contient-il déjà quelque chose ?

## 3. Étape 1 — Inventaire (lecture seule)

Sur l'**ancien pod**, une fois démarré (terminal web RunPod) :

```bash
cd /workspace && curl -fsSL -o 01_inventaire.sh \
  https://raw.githubusercontent.com/somet1010/suta-langues/claude/zen-euler-sigjls/runpod/01_inventaire.sh
bash 01_inventaire.sh
```

Produit `/workspace/_inventaire/manifeste-*.txt` (chemin + taille de chaque fichier)
et les empreintes SHA256 des fichiers critiques. **N'écrit rien ailleurs, ne supprime rien.**

Me renvoyer la sortie : elle décide de la taille du volume et du GPU nécessaires.

## 4. Étape 2 — Nouveau pod + copie

1. Créer un pod GPU **dans `EU-RO-1`** (même région que le volume) en attachant
   le Network Volume `suta-langues-test_volume` monté sur `/workspace`.
2. GPU : Spark-TTS 0.5B tient largement sous 24 Go de VRAM.
   Ordre de préférence : **RTX 4090 → RTX 3090 → A5000 → A40**, selon dispo et prix
   dans EU-RO-1. Pas de H100/H200/RTX PRO 6000 : surcoût sans bénéfice ici.
3. Exposer le port HTTP **7860** dès la création du pod.
4. Copier, depuis le **nouveau** pod (simulation d'abord) :

```bash
SRC_HOST=<ip_ancien_pod> SRC_PORT=<port_ssh_ancien_pod> bash 02_copie.sh --dry-run
SRC_HOST=<ip_ancien_pod> SRC_PORT=<port_ssh_ancien_pod> bash 02_copie.sh
```

`rsync` sans `--delete`, relançable sans tout recopier. Si les pods ne peuvent pas
se joindre en SSH : `02b_copie_runpodctl.sh` (pair-à-pair, dossier par dossier).

Le venv est restauré **au même chemin** `/workspace/maliba-venv` : ses chemins
absolus restent valides, donc pas de réinstallation.

## 5. Étape 3 — Vérification avant toute suppression

Sur le **nouveau** pod :

```bash
SRC_MAN=/workspace/_inventaire/manifeste-<tag>.txt bash 03_verification.sh
```

Sort en erreur si un élément critique manque. Tant qu'il n'est pas vert :
**aucun Terminate, aucun `rm`**.

## 6. Étape 4 — Relance du service

```bash
bash 04_relance_sparktts.sh
```

Vérifie venv + modèle + `nvidia-smi` + `pip check`, lance `webui.py` en détaché
(journal dans `/workspace/suta-langues.log`) et attend l'écoute sur `0.0.0.0:7860`.
Ouvrir ensuite l'URL HTTP du port 7860 via le bouton **Connect** du pod, et tester
une phrase → WAV.

## 7. Garde-fous

- Jamais de `rm -rf /workspace` : aucun script de ce dossier ne supprime quoi que ce soit.
- Aucun `Terminate` de l'ancien pod avant vérification verte **et** ton accord explicite.
- Les poids du modèle ne sont pas retéléchargés s'ils sont présents.
- Les dépendances ne sont pas réinstallées si `maliba-venv` fonctionne.
- Versions à préserver : `gradio==5.18.0`, `gradio-client==1.7.2`, `pydantic==2.10.6`.

## 8. Journal

| Date | Vérifié | Changé | Reste à faire |
|---|---|---|---|
| 2026-09-15 | Accès RunPod depuis la session : API, docs et SSH bloqués ; pas de clé API. Repo `somet1010/suta-langues` : pas de trace de la config RunPod/Spark-TTS. | Ajout du dossier `runpod/` : 5 scripts (inventaire, copie, copie de secours, vérification, relance) + ce runbook. | Réponses aux points « À DÉFINIR » §2, puis sortie de `01_inventaire.sh` sur l'ancien pod. |
