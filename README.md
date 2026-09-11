# SUTA-LANGUES

Service indépendant de transcription des langues ivoiriennes. SUTA l'appelle via
`LABO_ASR_ENDPOINT` sans modification de son code.

## Contrat SUTA

`POST /v1/transcrire`

```json
{"audio":"<base64>","mime":"audio/wav","lang":"dyu_Latn"}
```

Réponse :

```json
{"texte":"i ni ce","traduction":null,"lang":"dyu_Latn","modele":"omniASR_CTC_300M_v2","duree_ms":420}
```

`GET /v1/langues` renvoie les langues ivoiriennes activées — 24 langues, toutes
vérifiées dans la liste officielle du modèle (`lang_ids.py` d'omnilingual-asr
0.2.0, revérifiée le 11/09/2026). Leur présence dans le modèle est confirmée ;
leur qualité doit être mesurée avec des locuteurs (labo langues de SUTA).

## Clé d'accès

Définir `LANGUES_API_KEY` protège `/v1/transcrire` : l'appelant doit envoyer
`Authorization: Bearer <clé>` — côté SUTA c'est la variable `LABO_ASR_KEY`,
même valeur. Variable vide = service ouvert, acceptable UNIQUEMENT en
développement local ; en production la clé est obligatoire, en plus de la
passerelle réseau (voir Docker / Azure). La clé se transmet par le coffre à
secrets, jamais par messagerie.

## Lancer pour développer

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
uvicorn suta_langues.main:app --reload
```

Ouvrir `http://localhost:8000`. Sans l'option `asr`, les tests fonctionnent mais
la transcription réelle renvoie 503, volontairement.

## Lancer avec Omnilingual ASR

```bash
pip install -e '.[asr]'
OMNIASR_MODEL=omniASR_CTC_300M_v2 uvicorn suta_langues.main:app --host 0.0.0.0 --port 8000
```

Le modèle par défaut est le CTC 300M v2 (environ 1,3 Gio au téléchargement et
environ 2 Gio de VRAM selon Meta). Le premier appel télécharge et charge le modèle.
Pour le meilleur niveau de qualité sur GPU, définir par exemple
`OMNIASR_MODEL=omniASR_LLM_7B_v2`.

## Docker / Azure

```bash
docker build -t suta-langues .
docker run --gpus all -p 8000:8000 -e OMNIASR_MODEL=omniASR_CTC_300M_v2 suta-langues
```

Limiter l'accès réseau du conteneur en production, protéger l'API par la passerelle
Azure/API Management et ne pas journaliser le corps des requêtes audio.

