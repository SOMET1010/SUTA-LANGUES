# SUTA — vision et périmètre linguistique

> **Ce dépôt documente le patrimoine linguistique et la R&D** : modèles, corpus,
> langues, licences, ASR / TTS / compréhension, et les résultats de recherche.
>
> **Le produit vit ailleurs.** SUTA PASS — Android, offline/online, intentions,
> actions téléphone, intégration PASS — est développé dans `SOMET1010/SUTA-BOT`.
> Ne pas remélanger recherche de modèles et développement de l'assistant.

Reconstitué le **17/09/2026** à partir du fil de conversation de l'audit.

> ⚠️ **Avertissement sur la source.** La version précédente de ce document vivait
> dans un conteneur éphémère jamais poussé ; elle a été perdue. Ce fichier est une
> reconstitution : il ne contient que ce qui a survécu dans le fil. Les fiches
> détaillées de l'audit langue par langue (les dix langues) **ne sont pas
> récupérables** — seules leurs conclusions transversales figurent ici. Tout ce qui
> n'est pas explicitement marqué « vérifié » ne doit pas être traité comme acquis.

---

## Conventions de statut

Chaque affirmation porte un statut. **C'est la règle centrale de ce document :**
l'audit a produit plusieurs erreurs successives, et aucune ne doit se transformer
en vérité historique par simple recopie.

| Marque | Sens |
|---|---|
| ✅ **VÉRIFIÉ** | Constaté directement sur la source (fiche, données, métadonnées lues). Réutilisable. |
| 🟡 **HYPOTHÈSE** | Plausible, non établi. Ne jamais construire dessus sans vérification. |
| 🔵 **À REVALIDER** | Affirmé une fois, mais la preuve n'a pas été conservée ou l'identifiant exact manque. |
| ❌ **CONTREDIT** | Affirmé puis réfuté. Conservé exprès, pour que l'erreur ne revienne pas. |

Règle de méthode issue de l'audit, valable pour la suite :
**lire les données, jamais la fiche** — trois fiches de dépôt se sont révélées
fausses ou vides en une journée. Et **l'identifiant exact, jamais la devinette** —
trois tentatives ont échoué sur la casse et le préfixe d'un seul jeu de données.

---

## 1. Décisions actées (17/09/2026)

| Sujet | Décision |
|---|---|
| **Découpage des dépôts** | `SUTA-LANGUES` = patrimoine linguistique et R&D. `SUTA-BOT` = produit SUTA PASS. |
| **Langues V1** | Français + dioula + baoulé. Démarrage technique sur **une seule** langue locale autorisé si nécessaire. |
| **Priorité** | SUTA PASS V1 sur téléphone réel. **L'audit général ne reprend pas.** |
| **Pod GPU** | Autorisé **uniquement** pour une tâche précise et mesurée. Pas pour une recherche générale. |
| **Koumankan** | Reste en liste « accès à obtenir ». L'acceptation du dépôt est traitée séparément. |
| **Common Voice baoulé, 7 167 clips** | **Chiffre non confirmé** tant que la source exacte n'est pas retrouvée. |

Décision antérieure **périmée** : « dioula d'abord ». Elle avait été prise quand
nous croyions le dioula le mieux doté des langues ivoiriennes. L'audit a montré
que ce n'est pas le cas. Remplacée par la ligne « Langues V1 » ci-dessus.

---

## 2. La thèse centrale de l'audit

> ✅ **VÉRIFIÉ — Licence et domaine sont disjoints, sans exception constatée.**
>
> Dans tout le périmètre audité, ce qui est librement licencié est liturgique, et
> ce qui est vivant n'est pas ivoirien. La seule chaîne complète entièrement
> permissive (le nzema) repose de bout en bout — oreille, compréhension, voix — sur
> des Écritures lues. Ce n'est pas une coïncidence : c'est le seul texte parallèle
> massif qui existe dans ces langues, et tout l'écosystème s'est construit dessus.

Conséquence directe, et c'est le tournant méthodologique de la journée :
**traduire est probablement la mauvaise approche.** Pour JULABA comme pour PASS,
il ne s'agit pas de rendre une phrase mais de **reconnaître une intention** —
vente, caisse, montant, stock, crédit, clôture. Une dizaine d'intentions se
classent avec bien moins de données qu'il n'en faut pour traduire, et cela
contourne entièrement le mur du domaine.

Les deux chiffres qui fondent ce basculement :

- ✅ **chrF++ 18,2** — meilleur traducteur baoulé disponible, en langage quotidien.
- ✅ **93,7 % d'exactitude** en détection d'intention après affinage sur langues
  africaines peu dotées (Injongo, cf. §7).

L'écart n'est pas marginal, il est structurel. **Reconnaître marche là où traduire
s'effondre**, et c'est maintenant mesuré, plus supposé.

---

## 3. Faits vérifiés — corpus

### 3.1 RobotsMali/afvoices — la meilleure ressource libre de la famille mandingue

- ✅ Revendiqué et confirmé sur la fiche : *« the largest open corpus of
  spontaneous Bambara speech »*.
- ✅ **423 h segmentées**, 612 h brutes. Sud du Mali. Enregistrement en situation
  naturelle et conversationnelle. Transcription par pré-étiquetage ASR puis
  correction humaine.
- ✅ Licence **CC-BY-4.0** — CC-BY simple, sans clause de partage à l'identique,
  donc **sans contamination** des modèles qui en dériveraient.
- ✅ Volumes réels : `human-corrected` 253 300 lignes / 57,8 Go ·
  `model-annotated` 355 600 · `short` 259 200 — **874 800 lignes** au total.
- ✅ Schéma : `text`, `duration`, `audio`, `label-v1`, `label-v2`.
- ✅ **2,6 × kunkado**, et sous une licence plus propre.
- ⚠️ **Il est malien, pas ivoirien.** C'est sa limite pour SUTA.

### 3.2 african-speech-ipa — le corpus liturgique

- ✅ Config `nzema_nzi` : **21,14 h, CC-BY-4.0**.
- ✅ **Même corpus Watchtower que la config `jula_dyu`.** Preuve textuelle relevée
  dans `nzema_nzi` : *« Gyihova Baboa Wɔ Yeamaa Wɔagyinla… »*,
  *« EDWƐNE 44 Anwunvɔnenli Asɔneyɛlɛ »*,
  *« …na yɛze kɛ… ( Wlo. 8:35-39 ) … Baebolo nu ngyinlazo… ( Aye. 48:17, 18 ) »* —
  Jéhovah, numérotation des cantiques (exactement le « DƆNKILI 134 » dioula), la
  Bible, références aux Romains et à Isaïe.
- ✅ **Trois défauts techniques identiques dans les deux configs** : les chiffres
  supprimés par le G2P (`8:35-39` devient `: -`), les titres non alignés
  (« EDWƐKƐ 17 », deux mots, pour 9,85 secondes d'audio), et la parole lue.
- 🔵 **À REVALIDER** : l'identifiant exact du dépôt (relevé dans le fil comme
  `AfriSpeech/african-speech-ipa`). À reconfirmer avant tout usage — la casse et le
  préfixe nous ont déjà coûté trois tentatives ailleurs.

### 3.3 kunkado

- ✅ Seule ressource à la fois **libre et vivante** de tout l'audit. En **bambara**.
- ✅ Les insertions françaises sont balisées par `__`, donc le taux réel de
  code-switching est **calculable exactement** au lieu d'être cru sur parole.
- 🔵 **À REVALIDER** : sa licence exacte. Le fil la présente comme moins propre que
  le CC-BY-4.0 d'afvoices, ce qui suggère une clause de partage à l'identique —
  **c'est une inférence, pas une lecture.**
- ⏸️ Mesure du code-switching : **en attente**, demande un pod (cf. §9).

### 3.4 Corpus métier et administratifs ivoiriens — le vide

- ✅ **Rien.** Aucun corpus de dialogue commercial, d'intentions bancaires ou de
  chiffres parlés en dioula, baoulé ou bambara-CI. Ni ouvert, ni fermé.
- ✅ Les déploiements réels existent mais sont **tous propriétaires** : CocoaLink
  (cacao), des chatbots en nouchi, EMY 101 côté administration. Ils prouvent le
  besoin sans fournir la matière.
- 🟡 **HYPOTHÈSE** : le baoulé et le bété seraient absents du projet *African Next
  Voices*. Source unique : un article de presse ivoirien. Non vérifié à la source.

---

## 4. Faits vérifiés — compréhension

### 4.1 google/madlad400-3b-mt — la seule voie permissive vers le baoulé

- ✅ **Apache-2.0**. T5, **2,9 milliards de paramètres**, 4,6 M de téléchargements.
- ✅ Étiquettes de langue lues directement : **`bm`, `dyu`, `bci` et `nzi` y sont**.
- ✅ **Absents** : `adj`, `ati`, `abi`, `gud`, `dnj`, `abr`, `ebr`.
  *(Gloses ISO 639-3 : adioukrou, attié, abidji, dida-Yocoboué, dan, abron, ébrié —
  à confirmer contre la liste officielle du projet.)*
- ✅ C'est la **première voie permissive vers la compréhension du baoulé**. NLLB ne
  connaît pas `bci` du tout.
- ⚠️ **La qualité par langue n'est pas publiée.** Présence ≠ qualité. À auditionner.
- 🔵 **À REVALIDER** : le décompte « quatre de tes dix langues ». La liste des dix
  langues du périmètre n'a pas survécu à la perte du document — **À DÉFINIR**, à
  restater avant de recompter.

### 4.2 Voies fermées

- ✅ **Similarité sémantique sans entraînement : fermée.** Ni LaBSE, ni
  multilingual-e5, ni AfroXLMR, ni AfriBERTa ne couvrent nos trois langues.
- ✅ **Aucun benchmark d'intention** n'existe pour elles.
- ✅ **Aucun précédent publié** de parole → intention sans transcription pour une
  langue ivoirienne ou mandingue. Ce n'est pas une lacune bibliographique, c'est un
  vide réel.

### 4.3 Le signal positif

- ✅ **SIB-200** : un XLM-R classe le **bambara et le dioula à ~49 %** sur sept
  catégories, contre **14 % au hasard**. La classification tient là où la traduction
  s'effondre — exactement ce que l'hypothèse prédisait.

### 4.4 Serengeti

- ✅ **Licence absente de sa fiche.** Candidat bambara **inutilisable en production**
  sans clarification.

---

## 5. Faits vérifiés — voix (TTS)

### 5.1 La voix baoulé permissive — requalifiée

Présentée un temps comme la trouvaille la plus prometteuse de l'audit. Elle ne
l'est plus.

- ✅ C'est le **seul composant vocal permissif** de toute la cartographie.
- ✅ Fiche **entièrement vide** : ni corpus, ni heures, ni locuteurs, ni parole lue
  ou spontanée, ni métrique, ni confirmation dialectale. Seulement : Apache-2.0,
  ESPnet2 + VITS, et trois lignes d'inférence.
- ✅ **Le jeu de données d'entraînement n'est pas publié.** Le compte expose
  **22 modèles et zéro jeu de données**. Le corpus n'est donc pas seulement non
  documenté : il est **indisponible**. La voix n'est ni reproductible, ni auditable.
- ✅ Datée de **mai 2022**, voisine de `test-model`, `test-model-lg-data`, d'essais
  Common Voice et d'un classifieur de tweets COVID. **Prototype de recherche, pas
  voix de production.**
- 🔵 **À REVALIDER** : l'identifiant exact du modèle (relevé comme
  `afrilang-bci-tts`) et celui du compte.

> **Statut retenu : à auditionner avant toute chose, jamais à inscrire comme acquis.**

### 5.2 Le mur du TTS n'est pas tombé

- ❌ **CONTREDIT — mon propre espoir.** J'ai cherché un identifiant de locuteur dans
  `afvoices`, espérant qu'il puisse nourrir une voix et non seulement une oreille.
  **Il n'y en a pas** (schéma : `text`, `duration`, `audio`, `label-v1`, `label-v2`).
- ✅ Conséquence : comme kunkado et comme le corpus IPA dioula, **afvoices sert
  l'oreille, pas la voix.** Le mur du TTS tient.

---

## 6. Licences — ce que l'audit a appris

> ✅ **Une licence apposée sur un artefact dont les données d'entraînement sont
> inconnues est un confort juridique, pas une garantie.**

Trois cas constatés, à garder en mémoire :

1. ✅ **Apache-2.0 sur un modèle sans corpus** (la voix baoulé). Le tag ne dit rien
   de ce qui a été ingéré.
2. ✅ **CC-BY-4.0 revendiqué sur des enregistrements Watchtower.** La revendication
   ne vaut pas titre.
3. ✅ **La licence permissive ne remonte pas jusqu'au socle.**
   `McGill-NLP/gemma-2-9b-it-Injongo-intent` est en CC-BY-4.0, mais son modèle de
   base `google/gemma-2-9b-it` est soumis aux **Gemma Terms of Use**, qui ne sont
   pas une licence ouverte au sens strict et imposent leurs propres restrictions
   d'usage. **Le CC-BY-4.0 porte sur l'affinage seul.**
   🔵 **À REVALIDER** : la « contamination MMS » constatée le même jour, décrite
   comme le même mécanisme en sens inverse. Le détail n'a pas survécu à la perte du
   document — à réétablir avant d'être invoqué.

---

## 7. Annexe méthodologique — la taxonomie Injongo

> ⚠️ **Référence de méthode, PAS taxonomie SUTA.** Les 40 intentions sont
> confirmées, mais **elles ne couvrent pas nos usages PASS / JULABA**. Ce qui se
> reprend ici, c'est le **format**, le **protocole de collecte** et surtout le
> **dimensionnement**. Pas la liste.

### 7.1 Ce que le projet démontre

- ✅ Article long **ACL 2025**, arXiv **2502.09814**. Dépôt McGill-NLP + collection
  Hugging Face.
- ✅ **93,7 %** d'exactitude en détection d'intention après affinage.
- ✅ **85,6 de F1** en slot-filling.
- ✅ **GPT-4o plafonne à 26 de F1** sur le même slot-filling. Les grands modèles
  génériques échouent là où un petit modèle affiné réussit.
- ✅ **Les énoncés ont été produits par des locuteurs natifs, pas traduits de
  l'anglais** — et les auteurs montrent que les énoncés d'**origine culturelle
  africaine transfèrent mieux** que les traductions occidentales. C'est la
  validation directe de notre approche de collecte.
- ✅ Le **domaine bancaire** y figure : c'est le plus proche de JULABA.

### 7.2 Le jeu de données — `masakhane/InjongoIntent` ✅ vérifié le 17/09/2026

- ✅ **Apache-2.0.** Créé le 13/11/2024, mis à jour le 04/01/2025. 53,6 K lignes,
  6,6 K téléchargements. Contact : `david.adelani@mila.quebec`. Dérivé de
  `clinc/clinc_oos`.
- ✅ **17 langues** : amh, ewe, hau, ibo, kin, lin, lug, orm, sna, sot, swa, twi,
  wol, xho, yor, zul + eng. **Aucune des nôtres** — ni `bm`, ni `dyu`, ni `bci`,
  ni `nzi`. Gabarit, jamais composant.
- ✅ **40 intentions exactement.** Cycle vérifié dans les données : la ligne 40 du
  split anglais reprend `translate`.
- ✅ Champs : `intent`, `text`, `spans` (`start_byte`, `limit_byte`, `label`),
  `target`, `example_id`. Le split `eng` ajoute `raw`.
- ❌ **La fiche du dépôt est fausse.** Elle décrit GSM8k — « grade school math
  problem », champs `question` / `answer`, 15 langues dont le vai. Copier-coller
  jamais corrigé. **Seules les données comptent.**
- ❌ **CONTREDIT** — « 3 200 phrases par langue », avancé par un agent. Le compte
  réel est **~3 160** (2 200 + 320 + 640). L'ordre de grandeur tenait, le chiffre
  non.
- ❌ **CONTREDIT** — « Injongo est publié chez McGill-NLP ou Masakhane (majuscule) ».
  Trois tentatives échouées sur la casse et le préfixe. Le bon identifiant est
  **`masakhane/InjongoIntent`**, en minuscules.

### 7.3 Le dimensionnement — c'est ce qu'il faut retenir

> ✅ **55 énoncés d'entraînement + 8 de validation + 16 de test, par intention.**

C'est **ce volume-là** qui produit les 93,7 %. Il est mesuré, pas estimé : 2 200 ÷ 40
en entraînement, 320 ÷ 40 en validation, 640 ÷ 40 en test — le split de validation
est trié par intention, 8 exemples chacune, ce qui a permis de vérifier le compte
des deux côtés.

**Conséquence pour notre collecte :** la fourchette « 50 à 150 énoncés oraux réels
par intention, auprès de vraies commerçantes » est confirmée par le bas. Dix
intentions × ~80 énoncés ≈ **800 énoncés** pour une V1 — sans commune mesure avec ce
qu'exigerait un traducteur.

### 7.4 Les 40 intentions (référence, à ne pas recopier telle quelle)

| Domaine | Intentions |
|---|---|
| **Bancaire / argent** (11) | `balance`, `bill_balance`, `exchange_rate`, `freeze_account`, `interest_rate`, `min_payment`, `pay_bill`, `pin_change`, `spending_history`, `transactions`, `transfer` |
| **Restauration / cuisine** (8) | `cook_time`, `food_last`, `ingredients_list`, `meal_suggestion`, `recipe`, `restaurant_reservation`, `restaurant_reviews`, `restaurant_suggestion` |
| **Voyage / hébergement** (8) | `book_flight`, `book_hotel`, `car_rental`, `confirm_reservation`, `international_visa`, `plug_type`, `travel_notification`, `travel_suggestion` |
| **Agenda / appareil** (9) | `alarm`, `calendar_update`, `cancel_reservation`, `make_call`, `play_music`, `share_location`, `shopping_list_update`, `text`, `update_playlist` |
| **Temps / langue** (4) | `time`, `timezone`, `translate`, `weather` |

### 7.5 Les 20 types d'entités

`ACCOUNT_TYPE`, `ARTIST_NAME`, `BANK_NAME`, `BILL_TYPE`, `CALENDAR_EVENT`,
`CITY_OR_PROVINCE`, `COUNTRY`, `CURRENCY`, `DATE`, `DISH_OR_FOOD`, `HOTEL_NAME`,
`LANGUAGE_NAME`, `MEAL_PERIOD`, `MONEY`, `NUMBER`, `PAYMENT_COMPANY`,
`PERSONAL_NAME`, `PLACE_NAME`, `RESTAURANT_NAME`, `TIME`

### 7.6 L'écart avec nos besoins

- ❌ **Les 11 intentions bancaires ne couvrent pas JULABA.** Rien pour la **vente**,
  rien pour le **stock**, rien pour la **clôture de caisse**. Le recouvrement porte
  au mieux sur `transfer`, `balance`, `transactions`, `spending_history`, `pay_bill`.
- ✅ **Directement réutilisables en revanche** : les slots `MONEY`, `NUMBER`,
  `CURRENCY`, `DATE`, `PERSONAL_NAME`, et le format `spans` / `target`.
- ⚠️ Les actions téléphone de PASS (`make_call`, `text`, `alarm`,
  `calendar_update`, `share_location`, `play_music`) ont des équivalents ici —
  **mais leur spécification appartient à `SUTA-BOT`**, pas à ce dépôt.

### 7.7 Le modèle affiné — `McGill-NLP/gemma-2-9b-it-Injongo-intent`

- ✅ gemma2, **9,24 milliards de paramètres**, **CC-BY-4.0**.
- ✅ Langues : en, am, ee, ha, ig, rw, ln, om, sn, sot, sw, tw, wo, xh, yo, zu, lg.
  **Aucune des nôtres** — gabarit, pas composant.
- ⚠️ Réserve juridique : cf. §6, point 3. Le socle Gemma impose ses propres
  restrictions.

---

## 7bis. WAXAL — vérifié le 20/09/2026

Jeu de parole africaine publié par Google Research (annonce du 03/02/2026),
collecté 2021-2024 par des partenaires africains qui en gardent la propriété.
Dépôt : `google/WaxalNLP`. Créé le 19/01/2026, **mis à jour le 01/09/2026**.
255,3 K téléchargements, 285 mentions. Article : arXiv **2602.02734**.

> **Des données, pas des modèles.** Aucun point de reprise ASR ou TTS n'est
> publié, et rien d'embarquable sur téléphone. Il faudrait entraîner soi-même.

### La question posée : nos langues y sont-elles ?

✅ **NON.** Aucune langue cible de SUTA / JULABA parmi les 29 codes déclarés :
ni `dyu` (dioula), ni `bci` (baoulé), ni sénoufo, ni bété, ni français.

⚠️ **Le piège à ne pas retomber dedans** : `bau` **n'est PAS le baoulé**.
En ISO 639-3, `bau` = Bada (Nigeria) ; le baoulé est `bci`. La ressemblance
des codes a de quoi tromper une lecture rapide.

Les 29 codes déclarés : `ach aka amh bau dag dga ewe fat ful hau ibo kik kpo
lin lug luo mas mlg nyn orm pcm sid sna sog swa tir twi wal yor`.

### ✅ Ce que la fiche NE déclare PAS — et qui est pourtant dans le dépôt

C'est la trouvaille du jour, et elle ne se voit pas sur la page du jeu.

Le front-matter du `README.md` porte **trois entrées mises en commentaire** —
`# - bam`, `# - fuf`, `# - wol` — ainsi qu'un bloc `# - config_name: bam_tts`
entièrement commenté. Or les fichiers, eux, **sont bien publiés** :

| Répertoire | État | Contenu mesuré |
|---|---|---|
| `data/TTS/bam` | **non déclaré** | 26 fichiers parquet — train ≈ **4,01 Go** (20 fichiers), validation ≈ 517 Mo, test ≈ 552 Mo. **≈ 5,08 Go au total.** |
| `data/TTS/wol` | non déclaré | présent |
| `data/TTS/fuf` | non déclaré | présent |

**Pour mesurer l'ordre de grandeur** : le TTS twi déclaré tient dans UN fichier
d'entraînement de 511 Mo. Le bambara non déclaré en compte vingt, pour huit fois
le volume. Ce n'est pas un résidu — c'est l'un des plus gros volets TTS du jeu.

🔵 **CE QUI RESTE À VÉRIFIER, et il ne faut rien en conclure avant :**
- **Le contenu.** Je n'ai pas pu lire une seule ligne : le visualiseur ne sert
  pas une configuration non déclarée, et `huggingface.co` est bloqué en
  téléchargement direct depuis le conteneur. Ce qui est établi, c'est
  « 5 Go de parquet nommés `bam-*` dans un dossier TTS » — ni les heures, ni le
  nombre de locuteurs, ni parole lue ou spontanée.
- **Pourquoi c'est commenté.** Un embargo, un défaut de qualité, un problème de
  consentement sont des hypothèses aussi plausibles qu'un oubli. Ces fichiers
  peuvent disparaître à la prochaine mise à jour. **Ne pas bâtir dessus sans
  copie locale ni clarification auprès des partenaires.**
- **La licence exacte.** Voir ci-dessous.

### ⚠️ La licence n'est PAS simplement CC-BY-4.0

La fiche déclare **DEUX** licences : `cc-by-sa-4.0` **et** `cc-by-4.0`, sans
dire laquelle couvre quel volet. Présenter WAXAL comme « CC-BY-4.0, usage
commercial permis » est donc une simplification dangereuse : le **partage à
l'identique** de CC-BY-SA contamine les modèles qui en dérivent.

C'est exactement le mécanisme relevé au §6 — la licence affichée ne dit pas ce
qui s'applique à la partie qu'on utilise. **À trancher par volet avant tout
entraînement**, en particulier pour `bam`.

### Ce qui pourrait servir, et à quel titre

| Piste | Volume mesuré | Statut honnête |
|---|---|---|
| **`bam` TTS** (non déclaré) | ≈ 5,08 Go | La seule voix mandingue jamais croisée dans l'audit. **À auditionner et à sécuriser en priorité** — sous réserve de licence et de pérennité. |
| **`aka` / `twi` / `fat`** (akan) | aka ASR : 10,1 K énoncés transcrits + 175 K non transcrits | Le baoulé est une langue kwa du groupe tano, proche de l'akan. Base de transfert **crédible mais non démontrée** : c'est de la R&D, pas un composant. |
| **`ful`** (peul) | ASR ≈ 19,1 K énoncés · TTS ≈ 3,1 K phrases | Présent sur les marchés ivoiriens (bétail), mais hors du périmètre V1. |

### Conséquence sur la thèse centrale (§2)

Elle tient, et se précise. WAXAL est **libre et non liturgique** — ce qui est
rare — mais **aucune de nos langues n'y figure**. Le biais n'est plus seulement
« libre = liturgique » : il est aussi géographique. Le financement de la parole
africaine libre va vers l'Afrique de l'Est, le Ghana et le Nigeria. La Côte
d'Ivoire et le monde mandingue restent hors champ, sauf par la porte de service
d'un répertoire `bam` que personne n'a déclaré.

---

## 8. Registre des erreurs — à ne pas ressusciter

Section conservée volontairement. Chacune de ces affirmations a été tenue pour
vraie à un moment de l'audit, puis réfutée.

| # | Affirmation | Statut |
|---|---|---|
| 1 | « Monsia, auteur de la voix baoulé, est aussi à l'origine du corpus dioula de l'UVCI — la provenance ivoirienne de la voix est donc crédible. » | ❌ **CONTREDIT.** Aucune affiliation UVCI visible. Le gros du travail de 2024 porte sur l'anglais ↔ twi — **le Ghana, pas la Côte d'Ivoire.** L'hypothèse reposait sur un « Monsia commited on » aperçu dans l'historique de `uvci/koumankan4dyula`. |
| 2 | « La voix baoulé permissive est la trouvaille la plus prometteuse de l'audit. » | ❌ **CONTREDIT.** Prototype de 2022, corpus non publié, fiche vide, aucune métrique. Requalifiée : à auditionner, jamais à inscrire comme acquis. |
| 3 | « `afvoices` pourrait nourrir une voix — le mur du TTS va tomber. » | ❌ **CONTREDIT.** Pas d'identifiant de locuteur dans le schéma. |
| 4 | « Injongo est publié chez McGill-NLP / Masakhane (majuscule). » | ❌ **CONTREDIT.** C'est `masakhane/InjongoIntent`. |
| 5 | « Injongo : 3 200 phrases par langue. » | ❌ **CONTREDIT.** ~3 160. |
| 6 | « Common Voice v26 contient 7 167 clips baoulé. » | 🔵 **NON CONFIRMÉ** (décision du 17/09). Introuvable de mon côté — mais **je refuse de la déclarer fausse sur un résultat négatif.** La source exacte est à fournir. |
| 7 | « Le dioula est la mieux dotée des langues ivoiriennes, donc le MVP commence par le dioula. » | ❌ **PÉRIMÉ.** La seule ressource à la fois libre et vivante (kunkado) est en bambara, et afvoices est malien. Décision remplacée le 17/09. |
| 9 | « WAXAL est en CC-BY-4.0, usage commercial permis. » | 🔵 **À NUANCER.** La fiche déclare CC-BY-SA-4.0 **et** CC-BY-4.0, sans répartition publiée. Le partage à l'identique contaminerait les modèles dérivés. |
| 10 | « `bau` pourrait être le baoulé. » | ❌ **FAUX.** `bau` = Bada (Nigeria). Le baoulé est `bci`. Erreur évitée de justesse, consignée pour qu'elle ne revienne pas. |
| 8 | Fiches de dépôt fiables | ❌ **CONTREDIT trois fois en une journée** : fiche vide (voix baoulé), licence absente (Serengeti), fiche décrivant un autre jeu (InjongoIntent / GSM8k). |

---

## 9. Accès à obtenir et tâches bloquées

| Élément | Nature du blocage | Statut |
|---|---|---|
| `uvci/koumankan4dyula` (+ `Koumankan_mt_dyu_fr`, `flores-plus-fra-dyu`) | Dépôt fermé, conditions à accepter | **Accès à obtenir** — traité séparément. Clé de voûte du dioula, aujourd'hui **inauditable** : ni locuteurs connus, ni domaine des phrases. Après ce que l'audit a révélé du biais liturgique, c'est la vérification la plus utile qui reste. |
| `ghana-tts-72k` | Dépôt fermé | **Accès à obtenir** |
| `Dama12` | Dépôt fermé | **Accès à obtenir** |
| Source des 7 167 clips baoulé (Common Voice v26) | Introuvable | **Non confirmé** |
| Taux de code-switching de kunkado | Demande un pod | **Éligible** au pod : tâche précise et mesurée (les balises `__` rendent le chiffre exactement calculable). |
| Audition de la voix baoulé | Demande des phrases JULABA + un pod | **Éligible** au pod, une fois les phrases fournies. |
| Qualité par langue de MADLAD-400 (bci, dyu) | Non publiée | À mesurer — tâche pod candidate. |

---

## 10. Contrainte d'environnement constatée

- ✅ **`huggingface.co` est bloqué en HTTPS direct** par la politique de sortie du
  conteneur (403 sur le tunnel CONNECT). Seul le connecteur MCP Hugging Face passe.
- ⚠️ **Conséquence opérationnelle** : impossible de télécharger un `.jsonl` ou un
  `.parquet` pour le compter localement. Toute mesure sur données brutes — le
  code-switching de kunkado en premier — exige un pod, pour cette raison en plus
  des raisons de calcul.

---

## 11. Ce qui n'est pas dans ce document

Relèvent de `SOMET1010/SUTA-BOT` et ne doivent pas être traités ici :

- l'application **SUTA PASS** sur Android, son fonctionnement offline / online ;
- la **taxonomie d'intentions propre à PASS et à JULABA** — à construire, en
  s'inspirant du §7 pour le format et le dimensionnement, jamais de sa liste ;
- les **actions téléphone** et l'intégration PASS ;
- la collecte terrain auprès des commerçantes, son protocole et ses résultats.

**Prochaine étape validée : SUTA PASS V1 sur téléphone réel.** L'audit général ne
reprend pas.
