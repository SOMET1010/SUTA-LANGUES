#!/usr/bin/env python3
"""
WAXAL / bambara — sécuriser et mesurer le volet TTS non déclaré.

CONTEXTE (à lire avant de lancer)
---------------------------------
Le dépôt `google/WaxalNLP` publie un répertoire `data/TTS/bam` d'environ
5,08 Go qui n'est PAS déclaré dans la fiche : le front-matter du README porte
`# - bam` en commentaire, et le bloc `# - config_name: bam_tts` est désactivé.
Les fichiers sont pourtant bien là (constaté le 20/09/2026).

C'est la seule voix mandingue rencontrée dans tout l'audit SUTA-LANGUES. Deux
raisons de ne pas s'en réjouir trop vite, et ce script sert à les lever :

1. PÉRENNITÉ — ce qui n'est pas déclaré peut disparaître à la prochaine mise à
   jour. D'où le mode `--secure`, qui en fait une copie locale vérifiée.
2. CONTENU — personne n'a lu une ligne de ces fichiers. Ni heures, ni
   locuteurs, ni parole lue ou spontanée. D'où le mode `--inspect`.

L'audit a montré que le biais liturgique se détecte immédiatement dans les
transcriptions (Jéhovah, numérotation des cantiques, références bibliques).
`--inspect` applique ce test, parce qu'une voix mandingue libre qui serait
encore une lecture des Écritures ne changerait rien au problème.

PRÉREQUIS
---------
    pip install "huggingface_hub>=0.25" "pyarrow>=17"

USAGE
-----
    # Rapide, quelques Mo : schéma, lignes, heures, test liturgique.
    python waxal_bam.py --inspect --rapport rapport-bam.md

    # Lent, ~5,1 Go : copie locale vérifiée.
    python waxal_bam.py --secure --dest ./waxal-bam

    # Les deux, en mesurant sur la copie locale (plus fiable).
    python waxal_bam.py --secure --inspect --dest ./waxal-bam --rapport rapport-bam.md

NOTE SUR LA LICENCE
-------------------
La fiche déclare CC-BY-SA-4.0 ET CC-BY-4.0 sans dire laquelle couvre quel
volet. Le partage à l'identique contaminerait tout modèle dérivé. Ce script
MESURE ; il ne tranche pas la licence, et rien ne doit être entraîné sur ces
données avant que ce point soit éclairci auprès des partenaires.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import struct
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

DEPOT = "google/WaxalNLP"
PREFIXE = "data/TTS/bam"

# Tailles relevées le 20/09/2026, en octets. Un écart n'est pas forcément une
# erreur — le dépôt a pu être republié — mais il doit être VU, pas subi.
EMPREINTE_20260920 = {
    "fichiers": 26,
    "train": 20,
    "validation": 3,
    "test": 3,
    "octets_total": 5_079_435_336,
}

# Marqueurs du corpus Watchtower, relevés dans jula_dyu et nzema_nzi pendant
# l'audit. La casse et les accents sont ignorés au test.
MARQUEURS_LITURGIQUES = [
    r"\bjehovah\b", r"\bjehova\b", r"\bgyihova\b", r"\bjahovah\b",
    r"\bdonkili\b", r"\bedwene\b", r"\bedweke\b",
    r"\bbible\b", r"\bbaebolo\b", r"\bbibulu\b",
    r"\bmatie?\b\s*\d+[:.]\d+", r"\d+\s*[:.]\s*\d+\s*[-–]\s*\d+",
    r"\bapocalypse\b", r"\bpsaume\b", r"\bmarc\b\s*\d+",
]


# Les lettres propres aux orthographes mandingues et akan. NFD ne les
# décompose PAS et elles ne sont pas des marques combinantes : sans cette
# table, « DƆNKILI » ne rencontrerait jamais le motif `donkili`, et le test
# du biais liturgique passerait à côté du corpus qu'il est censé détecter.
# C'est le même piège que dans `packages/pass/src/langue.ts` côté SUTA-BOT.
LETTRES_OUEST_AFRICAINES = {
    "ɛ": "e", "Ɛ": "e",
    "ɔ": "o", "Ɔ": "o",
    "ɲ": "ny", "Ɲ": "ny",
    "ŋ": "n", "Ŋ": "n",
    "ɖ": "d", "Ɖ": "d",
    "ƒ": "f", "Ƒ": "f",
    "ʋ": "v", "Ʋ": "v",
    "œ": "oe", "Œ": "oe",
}


def _norm(texte: str) -> str:
    import unicodedata

    ramene = "".join(LETTRES_OUEST_AFRICAINES.get(c, c) for c in texte)
    sans = unicodedata.normalize("NFD", ramene)
    sans = "".join(c for c in sans if unicodedata.category(c) != "Mn")
    return sans.lower()


@dataclass
class Mesure:
    fichiers: int = 0
    octets: int = 0
    lignes_par_split: dict = field(default_factory=dict)
    colonnes: list = field(default_factory=list)
    heures_audio: float | None = None
    methode_duree: str = "non mesurée"
    locuteurs_distincts: int | None = None
    echantillons_texte: list = field(default_factory=list)
    liturgique_sur: int = 0
    liturgique_total: int = 0
    alertes: list = field(default_factory=list)


def _duree_entete_audio(brut: bytes) -> float | None:
    """Durée en secondes lue dans l'EN-TÊTE, sans décoder le signal.

    Décoder 5 Go d'audio pour connaître une durée serait absurde : WAV et FLAC
    portent l'information dans leurs premiers octets. Les autres formats
    rendent None plutôt qu'une estimation inventée.
    """
    # 42 octets : la taille d'un STREAMINFO FLAC complet, et moins qu'un
    # en-tête WAV canonique (44). Un seuil plus haut — 64 par exemple —
    # rejetterait des en-têtes parfaitement lisibles.
    if len(brut) < 42:
        return None
    # WAV : chercher le sous-bloc `data` et diviser par le débit.
    if brut[:4] == b"RIFF" and brut[8:12] == b"WAVE":
        pos, taux, canaux, bits = 12, None, None, None
        while pos + 8 <= len(brut):
            bloc = brut[pos : pos + 4]
            taille = struct.unpack("<I", brut[pos + 4 : pos + 8])[0]
            if bloc == b"fmt " and pos + 8 + 16 <= len(brut):
                _, canaux, taux, _, _, bits = struct.unpack(
                    "<HHIIHH", brut[pos + 8 : pos + 8 + 16]
                )
            elif bloc == b"data":
                if taux and canaux and bits:
                    octets_par_seconde = taux * canaux * (bits // 8)
                    if octets_par_seconde:
                        return taille / octets_par_seconde
                return None
            pos += 8 + taille + (taille % 2)
        return None
    # FLAC : le STREAMINFO porte le nombre d'échantillons et le taux.
    if brut[:4] == b"fLaC" and len(brut) >= 42:
        info = brut[8:42]
        taux = (info[10] << 12) | (info[11] << 4) | (info[12] >> 4)
        total = ((info[13] & 0x0F) << 32) | int.from_bytes(info[14:18], "big")
        if taux and total:
            return total / taux
    return None


def _lister_distant():
    from huggingface_hub import HfApi

    fichiers = HfApi().list_repo_tree(
        DEPOT, repo_type="dataset", path_in_repo=PREFIXE, recursive=True
    )
    return sorted(
        (f for f in fichiers if getattr(f, "size", None) and f.path.endswith(".parquet")),
        key=lambda f: f.path,
    )


def securiser(dest: Path) -> list[Path]:
    """Copie locale vérifiée du répertoire bam. ~5,1 Go."""
    from huggingface_hub import snapshot_download

    print(f"[secure] téléchargement de {PREFIXE} vers {dest} …", flush=True)
    dest.mkdir(parents=True, exist_ok=True)
    chemin = snapshot_download(
        repo_id=DEPOT,
        repo_type="dataset",
        allow_patterns=[f"{PREFIXE}/*"],
        local_dir=str(dest),
        max_workers=4,
    )
    locaux = sorted(Path(chemin, PREFIXE).glob("*.parquet"))
    octets = sum(p.stat().st_size for p in locaux)
    print(f"[secure] {len(locaux)} fichiers, {octets / 2**30:.2f} Gio")

    empreintes = {}
    for p in locaux:
        h = hashlib.sha256()
        with p.open("rb") as f:
            for bloc in iter(lambda: f.read(1 << 20), b""):
                h.update(bloc)
        empreintes[p.name] = h.hexdigest()
    (dest / "EMPREINTES-SHA256.json").write_text(
        json.dumps(empreintes, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(f"[secure] empreintes écrites dans {dest / 'EMPREINTES-SHA256.json'}")
    return locaux


def inspecter(locaux: list[Path] | None, max_textes: int = 400) -> Mesure:
    """Schéma, lignes, heures, locuteurs, test liturgique.

    Sans copie locale, lit les fichiers à distance : le pied de page parquet
    suffit pour le schéma et le compte de lignes, et seules les colonnes utiles
    sont chargées pour le reste.
    """
    import pyarrow.parquet as pq

    m = Mesure()

    if locaux:
        sources = [(p.name, str(p)) for p in locaux]
        ouvrir = lambda s: s
    else:
        from huggingface_hub import HfFileSystem

        fs = HfFileSystem()
        distants = _lister_distant()
        sources = [(Path(f.path).name, f"datasets/{DEPOT}/{f.path}") for f in distants]
        ouvrir = lambda s: fs.open(s, "rb")
        m.octets = sum(f.size for f in distants)

    m.fichiers = len(sources)
    if locaux:
        m.octets = sum(p.stat().st_size for p in locaux)

    colonne_duree = colonne_locuteur = colonne_texte = None
    locuteurs, textes = set(), []
    secondes_total, secondes_mesurees, lignes_mesurees = 0.0, 0, 0

    for nom, source in sources:
        split = "inconnu"
        for s in ("train", "validation", "test"):
            if f"-{s}-" in nom:
                split = s
        try:
            pf = pq.ParquetFile(ouvrir(source))
        except Exception as e:  # noqa: BLE001
            m.alertes.append(f"{nom} illisible : {type(e).__name__}: {e}")
            continue

        schema = pf.schema_arrow
        if not m.colonnes:
            m.colonnes = list(schema.names)
            bas = [c.lower() for c in schema.names]
            for cible, attr in (
                (("duration", "duree", "length", "seconds"), "colonne_duree"),
                (("speaker", "speaker_id", "locuteur", "voice"), "colonne_locuteur"),
                (("text", "transcript", "transcription", "sentence", "texte"), "colonne_texte"),
            ):
                for i, c in enumerate(bas):
                    if c in cible or any(c.startswith(t) for t in cible):
                        val = schema.names[i]
                        if attr == "colonne_duree":
                            colonne_duree = colonne_duree or val
                        elif attr == "colonne_locuteur":
                            colonne_locuteur = colonne_locuteur or val
                        else:
                            colonne_texte = colonne_texte or val
                        break

        m.lignes_par_split[split] = m.lignes_par_split.get(split, 0) + pf.metadata.num_rows

        voulues = [c for c in (colonne_duree, colonne_locuteur, colonne_texte) if c]
        if voulues:
            table = pf.read(columns=voulues)
            if colonne_duree:
                col = table.column(colonne_duree).to_pylist()
                secondes_total += sum(v for v in col if isinstance(v, (int, float)))
            if colonne_locuteur:
                locuteurs.update(
                    str(v) for v in table.column(colonne_locuteur).to_pylist() if v is not None
                )
            if colonne_texte and len(textes) < max_textes:
                for v in table.column(colonne_texte).to_pylist():
                    if isinstance(v, str) and v.strip():
                        textes.append(v.strip())
                        if len(textes) >= max_textes:
                            break

        # Pas de colonne de durée : on échantillonne les en-têtes audio du
        # premier groupe de lignes et on extrapole — en le DISANT.
        if colonne_duree is None and lignes_mesurees < 200:
            nom_audio = next(
                (c for c in schema.names if c.lower() in ("audio", "wav", "speech")), None
            )
            if nom_audio:
                try:
                    grp = pf.read_row_group(0, columns=[nom_audio]).column(nom_audio).to_pylist()
                except Exception:  # noqa: BLE001
                    grp = []
                for cellule in grp[:100]:
                    brut = cellule.get("bytes") if isinstance(cellule, dict) else None
                    if isinstance(brut, (bytes, bytearray)):
                        d = _duree_entete_audio(bytes(brut[:4096]))
                        if d:
                            secondes_total += d
                            secondes_mesurees += 1
                    lignes_mesurees += 1

    lignes_total = sum(m.lignes_par_split.values())
    if colonne_duree:
        m.heures_audio = secondes_total / 3600
        m.methode_duree = f"somme exacte de la colonne « {colonne_duree} »"
    elif secondes_mesurees:
        moyenne = secondes_total / secondes_mesurees
        m.heures_audio = moyenne * lignes_total / 3600
        m.methode_duree = (
            f"EXTRAPOLATION : {moyenne:.2f} s de moyenne sur {secondes_mesurees} "
            f"en-têtes audio, × {lignes_total} lignes. À confirmer."
        )
        m.alertes.append("Heures extrapolées, pas mesurées : traiter comme un ordre de grandeur.")
    else:
        m.alertes.append("Durée non mesurable : ni colonne de durée, ni en-tête audio exploitable.")

    m.locuteurs_distincts = len(locuteurs) if locuteurs else None
    if m.locuteurs_distincts == 1:
        m.alertes.append("Un seul locuteur : cohérent avec un volet TTS studio.")
    if colonne_locuteur is None:
        m.alertes.append(
            "Aucune colonne de locuteur — même limite que afvoices : sert l'oreille, pas la voix."
        )

    motifs = [re.compile(p) for p in MARQUEURS_LITURGIQUES]
    for t in textes:
        n = _norm(t)
        if any(p.search(n) for p in motifs):
            m.liturgique_sur += 1
    m.liturgique_total = len(textes)
    m.echantillons_texte = textes[:12]
    if m.liturgique_total and m.liturgique_sur / m.liturgique_total > 0.05:
        m.alertes.append(
            f"BIAIS LITURGIQUE PROBABLE : {m.liturgique_sur}/{m.liturgique_total} "
            "énoncés portent un marqueur Watchtower."
        )

    # Confrontation à l'empreinte du 20/09/2026.
    if m.fichiers != EMPREINTE_20260920["fichiers"]:
        m.alertes.append(
            f"Le dépôt a changé : {m.fichiers} fichiers au lieu de "
            f"{EMPREINTE_20260920['fichiers']} le 20/09/2026."
        )
    ecart = abs(m.octets - EMPREINTE_20260920["octets_total"])
    if m.octets and ecart > EMPREINTE_20260920["octets_total"] * 0.02:
        m.alertes.append(
            f"Volume différent de plus de 2 % : {m.octets:,} octets contre "
            f"{EMPREINTE_20260920['octets_total']:,} le 20/09/2026."
        )
    return m


def rendre_rapport(m: Mesure) -> str:
    lignes_total = sum(m.lignes_par_split.values())
    out = [
        "# WAXAL — volet bambara (`data/TTS/bam`), mesure",
        "",
        "> Volet **non déclaré** de `google/WaxalNLP` : présent dans le dépôt,",
        "> absent de la fiche. Rapport produit par `outils/waxal_bam.py`.",
        "",
        "## Volume",
        "",
        f"- Fichiers parquet : **{m.fichiers}**",
        f"- Taille : **{m.octets:,} octets** ({m.octets / 2**30:.2f} Gio)",
        f"- Lignes : **{lignes_total:,}**",
        "",
        "| Split | Lignes |",
        "|---|---:|",
    ]
    for split in ("train", "validation", "test", "inconnu"):
        if split in m.lignes_par_split:
            out.append(f"| {split} | {m.lignes_par_split[split]:,} |")
    out += [
        "",
        "## Contenu",
        "",
        f"- Colonnes : `{'`, `'.join(m.colonnes) if m.colonnes else '—'}`",
        f"- Heures d'audio : **{m.heures_audio:.1f} h**" if m.heures_audio else "- Heures : non mesurées",
        f"- Méthode : {m.methode_duree}",
        f"- Locuteurs distincts : "
        + (str(m.locuteurs_distincts) if m.locuteurs_distincts is not None else "inconnu (pas de colonne)"),
        "",
        "## Test du biais liturgique",
        "",
        "Marqueurs du corpus Watchtower relevés pendant l'audit sur `jula_dyu`",
        "et `nzema_nzi` : Jéhovah, numérotation des cantiques, références bibliques.",
        "",
        f"- Énoncés examinés : **{m.liturgique_total}**",
        f"- Portant un marqueur : **{m.liturgique_sur}**"
        + (f" ({100 * m.liturgique_sur / m.liturgique_total:.1f} %)" if m.liturgique_total else ""),
    ]
    if m.echantillons_texte:
        out += ["", "### Échantillons bruts", ""]
        out += [f"- « {t[:160]} »" for t in m.echantillons_texte]
    out += ["", "## Alertes", ""]
    out += [f"- ⚠️ {a}" for a in m.alertes] if m.alertes else ["- Aucune."]
    out += [
        "",
        "## Ce que ce rapport ne dit PAS",
        "",
        "- **La licence.** La fiche déclare CC-BY-SA-4.0 ET CC-BY-4.0 sans",
        "  répartition. Rien ne doit être entraîné avant clarification.",
        "- **Pourquoi c'est non déclaré.** Embargo, qualité, consentement sont",
        "  aussi plausibles qu'un oubli.",
        "- **La qualité perçue.** Aucune écoute n'a eu lieu.",
        "",
    ]
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--secure", action="store_true", help="copie locale vérifiée (~5,1 Go)")
    ap.add_argument("--inspect", action="store_true", help="mesurer schéma, heures, locuteurs, biais")
    ap.add_argument("--dest", type=Path, default=Path("./waxal-bam"))
    ap.add_argument("--rapport", type=Path, default=None)
    ap.add_argument("--json", type=Path, default=None)
    a = ap.parse_args()

    if not (a.secure or a.inspect):
        ap.error("choisir au moins --secure ou --inspect")

    locaux = securiser(a.dest) if a.secure else None
    if not a.inspect:
        return 0

    m = inspecter(locaux)
    rapport = rendre_rapport(m)
    print("\n" + rapport)
    if a.rapport:
        a.rapport.write_text(rapport, encoding="utf-8")
        print(f"[rapport] écrit dans {a.rapport}")
    if a.json:
        a.json.write_text(json.dumps(asdict(m), indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
