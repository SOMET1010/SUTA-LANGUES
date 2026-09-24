#!/usr/bin/env python3
"""
Vérifie les enregistrements et construit le jeu de données Piper.

POURQUOI CETTE ÉTAPE EXISTE
---------------------------
Un corpus de voix ne meurt presque jamais à l'entraînement : il meurt ici.
Un décalage d'un fichier entre l'audio et le texte, une fréquence qui change au
milieu de la séance, un micro qu'on a rapproché après la pause — et le modèle
apprend consciencieusement le défaut. On s'en aperçoit trois heures de GPU plus
tard, en écoutant.

Ce script regarde donc chaque fichier avant qu'un centime ne soit dépensé.

IL NE CONVERTIT RIEN, ET C'EST VOULU
------------------------------------
Rééchantillonner en silence masquerait un problème d'enregistrement. Si les
fichiers ne sont pas au bon format, mieux vaut les réexporter depuis la source
que les rafistoler ici : on perd dix minutes, on ne perd pas une séance.

USAGE
-----
    python3 outils/preparer_corpus_voix.py \
        --audio voix/brut \
        --script voix/script-enregistrement-fr.txt \
        --sortie voix/dataset

Sans --sortie, le script se contente de vérifier et de rapporter.
"""

from __future__ import annotations

import argparse
import array
import math
import pathlib
import re
import shutil
import sys
import wave

# --- Ce qu'on exige, et pourquoi ------------------------------------------

FREQUENCE_MIN = 22050      # en deçà, Piper perd les aigus de la voix
LARGEUR_ATTENDUE = 2       # 16 bits PCM
CANAUX_ATTENDUS = 1        # mono
DUREE_MIN = 0.4            # plus court : phrase tronquée au montage
DUREE_MAX = 20.0           # plus long : deux phrases dans un seul fichier
SILENCE_TETE_MAX = 1.5     # une longue amorce déséquilibre l'alignement
SILENCE_QUEUE_MAX = 2.0
SEUIL_SILENCE = 0.01       # amplitude normalisée sous laquelle on dit « silence »
ECART_NIVEAU_DB = 6.0      # écart toléré au niveau médian, avant de crier au micro déplacé
FICHIER_SILENCE = "0000"   # la prise de bruit de fond


class Probleme:
    BLOQUANT = "bloquant"
    ALERTE = "alerte"

    def __init__(self, gravite: str, fichier: str, message: str) -> None:
        self.gravite, self.fichier, self.message = gravite, fichier, message

    def __str__(self) -> str:
        marque = "✗" if self.gravite == Probleme.BLOQUANT else "!"
        return f"  {marque} {self.fichier:>8}  {self.message}"


class Mesure:
    def __init__(self, chemin: pathlib.Path) -> None:
        self.chemin = chemin
        self.identifiant = chemin.stem
        with wave.open(str(chemin), "rb") as w:
            self.canaux = w.getnchannels()
            self.largeur = w.getsampwidth()
            self.frequence = w.getframerate()
            self.trames = w.getnframes()
            brut = w.readframes(self.trames)
        self.duree = self.trames / self.frequence if self.frequence else 0.0
        self.echantillons: array.array | None = None
        if self.largeur == 2:
            ech = array.array("h")
            ech.frombytes(brut[: len(brut) - (len(brut) % 2)])
            if self.canaux > 1:  # on ne garde qu'un canal pour la mesure
                ech = array.array("h", ech[:: self.canaux])
            self.echantillons = ech

    @property
    def crete(self) -> float:
        if not self.echantillons:
            return 0.0
        return max(abs(v) for v in self.echantillons) / 32768.0

    @property
    def satures(self) -> int:
        if not self.echantillons:
            return 0
        return sum(1 for v in self.echantillons if v >= 32767 or v <= -32768)

    @property
    def rms_db(self) -> float:
        if not self.echantillons:
            return -120.0
        somme = sum(float(v) * v for v in self.echantillons)
        rms = math.sqrt(somme / len(self.echantillons)) / 32768.0
        return 20 * math.log10(rms) if rms > 0 else -120.0

    def _bords_parole(self) -> tuple[float, float]:
        """Durée de silence en tête et en queue, en secondes."""
        if not self.echantillons or not self.frequence:
            return 0.0, 0.0
        seuil = SEUIL_SILENCE * 32768
        debut = 0
        for i, v in enumerate(self.echantillons):
            if abs(v) > seuil:
                debut = i
                break
        else:
            return self.duree, self.duree
        fin = len(self.echantillons) - 1
        while fin > debut and abs(self.echantillons[fin]) <= seuil:
            fin -= 1
        return debut / self.frequence, (len(self.echantillons) - 1 - fin) / self.frequence

    @property
    def silence_tete(self) -> float:
        return self._bords_parole()[0]

    @property
    def silence_queue(self) -> float:
        return self._bords_parole()[1]


def lire_script(chemin: pathlib.Path) -> dict[str, str]:
    """Les phrases numérotées du script, indexées par leur numéro à quatre chiffres."""
    phrases: dict[str, str] = {}
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^(\d{4})\s\s+(.+?)\s*$", ligne)
        if m:
            phrases[m.group(1)] = m.group(2)
    return phrases


def verifier(mesures: list[Mesure], phrases: dict[str, str], bruit: Mesure | None) -> list[Probleme]:
    problemes: list[Probleme] = []
    par_id = {m.identifiant: m for m in mesures}

    # 1. La correspondance audio/texte — le défaut qui ruine tout le reste.
    manquants = sorted(set(phrases) - set(par_id))
    orphelins = sorted(set(par_id) - set(phrases))
    for identifiant in manquants:
        problemes.append(Probleme(Probleme.BLOQUANT, identifiant, "phrase du script sans enregistrement"))
    for identifiant in orphelins:
        problemes.append(Probleme(Probleme.BLOQUANT, identifiant, "enregistrement sans phrase correspondante"))

    # 2. Le format doit être IDENTIQUE partout : Piper entraîne à une seule
    #    fréquence, et un fichier qui détonne contamine tout le lot.
    frequences = {m.frequence for m in mesures}
    if len(frequences) > 1:
        problemes.append(Probleme(Probleme.BLOQUANT, "—", f"fréquences mélangées : {sorted(frequences)}"))

    for m in mesures:
        if m.frequence < FREQUENCE_MIN:
            problemes.append(Probleme(Probleme.BLOQUANT, m.identifiant, f"{m.frequence} Hz — minimum {FREQUENCE_MIN}"))
        if m.canaux != CANAUX_ATTENDUS:
            problemes.append(Probleme(Probleme.BLOQUANT, m.identifiant, f"{m.canaux} canaux — mono attendu"))
        if m.largeur != LARGEUR_ATTENDUE:
            problemes.append(Probleme(Probleme.BLOQUANT, m.identifiant, f"{m.largeur * 8} bits — 16 attendus"))
        if m.duree < DUREE_MIN:
            problemes.append(Probleme(Probleme.BLOQUANT, m.identifiant, f"{m.duree:.2f} s — phrase tronquée ?"))
        elif m.duree > DUREE_MAX:
            problemes.append(Probleme(Probleme.ALERTE, m.identifiant, f"{m.duree:.1f} s — deux phrases en un fichier ?"))
        if m.satures > 10:
            problemes.append(Probleme(Probleme.BLOQUANT, m.identifiant, f"saturation : {m.satures} échantillons écrêtés"))
        elif m.crete > 0.99:
            problemes.append(Probleme(Probleme.ALERTE, m.identifiant, f"crête à {m.crete:.3f} — au bord de la saturation"))
        if m.silence_tete > SILENCE_TETE_MAX:
            problemes.append(Probleme(Probleme.ALERTE, m.identifiant, f"{m.silence_tete:.1f} s de silence en tête"))
        if m.silence_queue > SILENCE_QUEUE_MAX:
            problemes.append(Probleme(Probleme.ALERTE, m.identifiant, f"{m.silence_queue:.1f} s de silence en queue"))

    # 3. La régularité du niveau : c'est ainsi qu'on détecte un micro déplacé
    #    entre deux prises, ou une séance reprise un autre jour.
    niveaux = sorted(m.rms_db for m in mesures if m.echantillons)
    if niveaux:
        median = niveaux[len(niveaux) // 2]
        for m in mesures:
            ecart = m.rms_db - median
            if abs(ecart) > ECART_NIVEAU_DB:
                problemes.append(
                    Probleme(Probleme.ALERTE, m.identifiant, f"niveau {ecart:+.1f} dB du médian — micro déplacé ?")
                )

    # 4. Le bruit de fond, mesuré sur la prise de silence.
    if bruit is None:
        problemes.append(Probleme(Probleme.ALERTE, FICHIER_SILENCE, "prise de bruit de fond absente"))
    elif bruit.rms_db > -50:
        problemes.append(
            Probleme(Probleme.ALERTE, FICHIER_SILENCE, f"pièce bruyante : {bruit.rms_db:.0f} dB (viser sous -50)")
        )
    return problemes


def construire(mesures: list[Mesure], phrases: dict[str, str], sortie: pathlib.Path) -> int:
    """Arborescence attendue par piper_train.preprocess : metadata.csv + wav/."""
    wavs = sortie / "wav"
    wavs.mkdir(parents=True, exist_ok=True)
    lignes = []
    for m in sorted(mesures, key=lambda x: x.identifiant):
        texte = phrases.get(m.identifiant)
        if texte is None:
            continue
        shutil.copy2(m.chemin, wavs / f"{m.identifiant}.wav")
        # Format single-speaker de Piper : id|texte. Le séparateur étant la
        # barre verticale, on la retire du texte plutôt que de casser le CSV.
        lignes.append(f"{m.identifiant}|{texte.replace('|', ' ')}")
    (sortie / "metadata.csv").write_text("\n".join(lignes) + "\n", encoding="utf-8")
    return len(lignes)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--audio", type=pathlib.Path, required=True, help="dossier des WAV bruts")
    ap.add_argument("--script", type=pathlib.Path, required=True, help="script d'enregistrement numéroté")
    ap.add_argument("--sortie", type=pathlib.Path, default=None, help="jeu de données à construire")
    ap.add_argument("--forcer", action="store_true", help="construire malgré les problèmes bloquants")
    a = ap.parse_args()

    phrases = lire_script(a.script)
    if not phrases:
        print(f"Aucune phrase numérotée trouvée dans {a.script}", file=sys.stderr)
        return 2

    fichiers = sorted(p for p in a.audio.glob("*.wav"))
    if not fichiers:
        print(f"Aucun WAV dans {a.audio}", file=sys.stderr)
        return 2

    mesures, bruit = [], None
    for chemin in fichiers:
        try:
            m = Mesure(chemin)
        except (wave.Error, EOFError) as e:
            print(f"  ✗ {chemin.name} illisible : {e}", file=sys.stderr)
            return 2
        if m.identifiant == FICHIER_SILENCE:
            bruit = m
        else:
            mesures.append(m)

    problemes = verifier(mesures, phrases, bruit)
    bloquants = [p for p in problemes if p.gravite == Probleme.BLOQUANT]
    alertes = [p for p in problemes if p.gravite == Probleme.ALERTE]

    duree_totale = sum(m.duree for m in mesures)
    print(f"{len(mesures)} enregistrements · {len(phrases)} phrases au script")
    print(f"durée utile : {duree_totale / 60:.1f} min · moyenne {duree_totale / max(len(mesures), 1):.1f} s")
    if bruit:
        print(f"bruit de fond : {bruit.rms_db:.0f} dB")
    print()

    if bloquants:
        print(f"BLOQUANTS ({len(bloquants)}) — à corriger avant d'entraîner")
        for p in bloquants[:40]:
            print(p)
        if len(bloquants) > 40:
            print(f"  … et {len(bloquants) - 40} autres")
        print()
    if alertes:
        print(f"Alertes ({len(alertes)}) — à regarder, pas forcément à corriger")
        for p in alertes[:25]:
            print(p)
        if len(alertes) > 25:
            print(f"  … et {len(alertes) - 25} autres")
        print()
    if not problemes:
        print("Aucun problème détecté.\n")

    if a.sortie is None:
        return 1 if bloquants else 0
    if bloquants and not a.forcer:
        print("Construction refusée : corrigez les bloquants, ou passez --forcer.", file=sys.stderr)
        return 1

    n = construire(mesures, phrases, a.sortie)
    print(f"Jeu de données écrit : {a.sortie} — {n} paires audio/texte")
    print(f"Fréquence à passer à Piper : {mesures[0].frequence}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
