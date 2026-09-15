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

### 0 bis. MCP RunPod — où il fonctionne, où il ne fonctionne pas

RunPod publie deux serveurs MCP officiels :

| Serveur | Endpoint |
|---|---|
| RunPod API (pods, volumes, templates, dispo GPU) | `https://mcp.getrunpod.io/` |
| RunPod Docs | `https://docs.runpod.io/mcp` |

Testé le 2026-09-15 **depuis la session cloud** : `mcp.getrunpod.io` et
`docs.runpod.io` sont refusés par le proxy de sortie (`registry.npmjs.org` répond
200, donc c'est bien une liste d'autorisation, pas une panne). `claude mcp add`
enregistre le serveur puis s'arrête sur `! Needs authentication` — et l'OAuth
exige un navigateur interactif, absent d'une session headless.

**Le MCP doit donc tourner sur la machine de l'utilisateur** (Claude Code sous
Windows, ou Claude Desktop), pas dans la session cloud :

```bash
# automatique (détecte Claude Code, Claude Desktop, Cursor, Windsurf, VS Code)
npx @runpod/mcp-server@latest add

# ou manuel, pour Claude Code
claude mcp add --transport http runpod -s user https://mcp.getrunpod.io/
# puis /mcp -> Sign in with RunPod
```

Claude Desktop : **Settings → Connectors → Add custom connector →**
`https://mcp.getrunpod.io/`

Portée réelle à vérifier une fois connecté (`/mcp` puis demander la liste des
outils) : le MCP couvre le **plan de contrôle** RunPod — démarrer un pod, créer
un pod avec volume, exposer un port, lister les GPU disponibles. Rien ne garantit
qu'il donne un **shell dans le pod** : les commandes de ce runbook
(`01_inventaire.sh`, `05_s3_sauvegarde.sh`…) passent par le Web Terminal tant que
l'inverse n'est pas constaté.

## 1. Contrainte structurante à connaître avant de cliquer

Un Network Volume RunPod s'attache **à la création du pod** et se monte sur
`/workspace`. L'ancien pod a son **propre volume disque** sur `/workspace` : il ne
peut donc pas monter le Network Volume en plus au même endroit. La copie se fait
donc **de pod à pod**, pas par « rebranchement » du volume.

Deux chemins possibles, par ordre de préférence :

- **A — démarrage CPU (voie retenue)** : l'UI RunPod propose
  **Start → Start Pod using CPUs** sur `suta-langues-a40-migration`. C'est suffisant
  pour lire `/workspace`, inventorier et copier : aucune de ces opérations n'a besoin
  de GPU. On n'attend donc pas la disponibilité d'un GPU pour sauvegarder.
- **B — l'ancien pod ne démarre pas du tout, même en CPU** : les données sont
  bloquées dans son datacenter. Seul recours : support RunPod. **Ne pas terminer
  le pod**, ce serait la perte définitive.

Correctif (une version précédente de ce runbook affirmait le contraire, à tort) :
un pod arrêté **peut** être redémarré en mode CPU depuis l'UI. En mode CPU,
`nvidia-smi` ne répond pas et `torch.cuda.is_available()` vaut `False` — c'est
normal et sans effet sur l'inventaire ou la copie. Le GPU n'est requis qu'à
l'étape 4, sur le **nouveau** pod.

## 2. Faits constatés dans l'UI (captures du 2026-09-15)

| Élément | Valeur |
|---|---|
| Pod `suta-langues-a40-migration` | **EU-CZ-1**, RTX 3090 ×1 — celui qui porte les données |
| Pod `suta-langues-a40` | EU-CZ-1, RTX 3090 ×1 — doublon, contenu à vérifier |
| Pod `suta-langues-test` | **EU-RO-1**, RTX 4090 ×1 |
| Volume `suta-langues-test_volume` | 50 Go, **EU-RO-1**, ID `vn82f9ix44`, 3,50 $/mois |
| API S3 du volume | bucket `vn82f9ix44`, endpoint `https://s3api-eu-ro-1.runpod.io`, région `eu-ro-1` |
| ID du pod source | `evnhxolsqj8oz3` (Secure cloud) |
| État du pod source | **arrêté** (Compute : *Not running*) — volume 50 Go toujours facturé 0,014 $/h, **données intactes** |
| Disque du pod source | Volume disk **50 Go sur `/workspace`** + container disk 60 Go |
| Image | `runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404` |
| Redémarrage GPU | 0,50 $/h — inutile pour la sauvegarde |

⚠️ **Le volume source fait 50 Go et le Network Volume aussi.** Si `/workspace` est
rempli à plus de ~45 Go, archives + extraction ne tiendront pas : il faudra
agrandir le Network Volume avant la copie. L'inventaire tranche.

**Conséquence majeure : le pod source (EU-CZ-1) et le volume (EU-RO-1) ne sont pas
dans la même région.** Un Network Volume ne s'attache qu'à un pod de sa région :
l'ancien pod ne pourra jamais le monter. Mais le volume expose une **API S3**
joignable depuis n'importe où — c'est la voie retenue, et elle supprime le besoin
d'un second pod allumé pendant la copie.

Restent à confirmer :

1. **`suta-langues-test` (EU-RO-1) a-t-il déjà le volume monté sur `/workspace` ?**
   Si oui, pas de nouveau pod à créer pour l'étape 4.
2. Le volume est-il **vide** ou contient-il déjà des données ?
3. Volumétrie réelle de `/workspace` sur l'ancien pod → donnée par l'étape 3.
   50 Go au total ; prévoir archives + extraction.

## 3. Étape 1 — Inventaire (lecture seule)

Sur l'**ancien pod**, démarré via **Start → Start Pod using CPUs**, dans le
Web Terminal. D'abord un contrôle à l'œil nu, avant tout script :

```bash
ls -lah /workspace
```

`SUTA-LANGUES`, `Spark-TTS`, `maliba-venv` et `maliba-test.wav` doivent apparaître.
Ensuite seulement :

```bash
cd /workspace && curl -fsSL -o 01_inventaire.sh \
  https://raw.githubusercontent.com/somet1010/suta-langues/claude/zen-euler-sigjls/runpod/01_inventaire.sh
bash 01_inventaire.sh
```

Produit `/workspace/_inventaire/manifeste-*.txt` (chemin + taille de chaque fichier)
et les empreintes SHA256 des fichiers critiques. **N'écrit rien ailleurs, ne supprime rien.**

Me renvoyer la sortie : elle décide de la taille du volume et du GPU nécessaires.

## 4. Étape 2 — Sauvegarde vers le volume via l'API S3 (voie retenue)

Le bucket S3 **est** le Network Volume : ce qui est déposé dedans apparaîtra sous
`/workspace` sur le pod GPU d'EU-RO-1. Donc : pas de SSH entre pods, pas de second
pod allumé, et la barrière inter-région disparaît.

Chaque dossier part en **archive `tar.gz` streamée** — pas d'espace disque
consommé sur l'ancien pod, et les liens symboliques / bits exécutables du venv
sont préservés (un `aws s3 sync` brut les perdrait et casserait `maliba-venv`).

Prérequis : une clé S3 créée dans RunPod (**Settings → S3 API Keys**), exportée en
`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`.

```bash
pip install -q awscli
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
bash 05_s3_sauvegarde.sh
```

Puis, sur le pod GPU d'EU-RO-1 avec le volume monté sur `/workspace` :

```bash
bash 06_s3_restauration.sh
```

GPU visé pour l'étape 4 : `suta-langues-test` est déjà en **RTX 4090 / EU-RO-1**,
ce qui correspond au premier choix (Spark-TTS 0.5B tient largement sous 24 Go).
Exposer le port HTTP **7860** sur ce pod.

**Voie de secours** si l'API S3 pose problème : `02_copie.sh` (rsync pod à pod,
inter-région, plus lent) ou `02b_copie_runpodctl.sh` (pair-à-pair).

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
| 2026-09-15 | Accès RunPod depuis la session : `api.runpod.io`, `console.runpod.io`, `s3api-eu-ro-1.runpod.io`, docs et SSH **tous bloqués** par la politique réseau. Repo : aucune trace de la config RunPod/Spark-TTS. | Ajout du dossier `runpod/` : runbook + 7 scripts. | Sortie de `ls -lah /workspace` puis de `01_inventaire.sh` sur l'ancien pod démarré en CPU. |
| 2026-09-15 | MCP RunPod (`mcp.getrunpod.io`, `docs.runpod.io/mcp`) : bloqué par le proxy depuis la session cloud, `claude mcp add` s'arrête sur *Needs authentication*. | Section 0 bis : installation du MCP côté machine utilisateur. Entrée MCP de test retirée de la config. | Connecter le MCP sur le PC Windows, puis lui demander la liste de ses outils pour savoir s'il donne un shell dans le pod. |
| 2026-09-15 | Correction : le pod **peut** redémarrer en CPU (*Start Pod using CPUs*) — mon affirmation inverse était fausse. Constaté aussi : source en EU-CZ-1, volume en EU-RO-1, et volume accessible en S3. | Runbook corrigé ; voie S3 retenue à la place du transfert pod à pod ; ajout de `05_s3_sauvegarde.sh` et `06_s3_restauration.sh`. | Créer la clé S3 (Settings → S3 API Keys) ; confirmer si `suta-langues-test` monte déjà le volume. |
