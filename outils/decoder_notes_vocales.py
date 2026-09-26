#!/usr/bin/env python3
"""
Décode des notes vocales (Opus/Ogg) en WAV, pour rattraper une séance.

POURQUOI CET OUTIL EXISTE À PART
--------------------------------
`preparer_corpus_voix.py` n'a AUCUNE dépendance : il doit pouvoir tourner sur
un pod nu, et c'est lui qui dit la vérité sur un corpus. Décoder de l'Opus
demande au contraire une bibliothèque tierce. Mélanger les deux rendrait
l'outil de vérité ininstallable là où on en a le plus besoin.

Celui-ci est donc un outil de RATTRAPAGE, assumé comme tel. Il sert quand les
prises sont arrivées en notes vocales — ce qui arrive presque toujours à la
première séance — et qu'on veut quand même les écouter, les mesurer pour de
vrai, et tenter un essai d'entraînement avant de redemander une séance.

CE QU'IL NE FAIT PAS
--------------------
Il ne débruite pas, ne coupe pas les silences, et n'ajuste JAMAIS un fichier
par rapport à un autre. Rééchantillonner est déjà un compromis ; en ajouter
d'autres reviendrait à juger un maquillage plutôt qu'une voix.

LE GAIN GLOBAL, ET POURQUOI IL N'EST PAS UNE NORMALISATION
----------------------------------------------------------
Un décodeur Opus dépasse régulièrement ±1,0 : la reconstruction d'un signal
compressé n'est pas bornée par l'amplitude de l'original. Mesuré sur un lot
réel : 118 fichiers sur 160 au-dessus de 1,0, crête médiane 1,0023, soit
+0,02 dB. Borner chaque fichier à ±1,0 fabriquerait donc une « saturation »
qui n'existe pas dans la prise — et ferait accuser la personne qui a
enregistré d'une faute commise par le décodeur.

Un gain UNIQUE est donc calculé sur l'ensemble du lot, à partir de la crête la
plus haute, puis appliqué identiquement à tous les fichiers. Les écarts de
niveau entre prises sont préservés au décibel près : c'est eux qui révèlent un
micro déplacé en cours de séance, et une normalisation par fichier les
effacerait.

Reste que 1,0023 et 1,41 ne disent pas la même chose. Au-delà du seuil de
dépassement plausible d'un codec, c'est l'original qui était écrêté, et le
rapport le signale nommément.

SUR LA FRÉQUENCE CIBLE
----------------------
Par défaut 22050 Hz, parce que c'est la fréquence du seul point de départ
français disponible chez Piper (`fr/fr_FR/siwis/medium` — vérifié le 26/09/2026 :
il n'existe aucun modèle français en 16 kHz). Suréchantillonner depuis 16 kHz
n'invente RIEN : la bande au-dessus de 8 kHz restera vide, et la voix produite
sonnera sourde. C'est acceptable pour répondre à « est-ce que cette voix
tient ? », jamais pour une voix de production.

DÉPENDANCES
-----------
    pip install av soxr numpy

USAGE
-----
    python3 outils/decoder_notes_vocales.py --entree voix/brut --sortie voix/decode
"""

from __future__ import annotations

import argparse
import importlib.util
import pathlib
import sys
import wave

import av
import numpy as np
import soxr

# La règle de numérotation vit dans l'outil de vérité : on l'importe plutôt que
# de la réécrire, sans quoi les deux outils divergeraient un jour en silence.
_spec = importlib.util.spec_from_file_location(
    "pcv", pathlib.Path(__file__).resolve().parent / "preparer_corpus_voix.py"
)
_pcv = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("pcv", _pcv)
_spec.loader.exec_module(_pcv)
numero_du_nom = _pcv.numero_du_nom

FREQUENCE_CIBLE = 22050
EXTENSIONS_SOURCE = (".opus", ".ogg", ".m4a", ".mp3", ".aac")
# Au-delà, ce n'est plus le codec qui déborde : c'est la prise qui était trop
# forte. Mesuré : la reconstruction Opus dépasse de ~0,2 % en usage normal.
CRETE_PLAUSIBLE_CODEC = 1.05


def gain_global(cretes: dict[str, float]) -> float:
    """
    Le facteur unique à appliquer à TOUT le lot pour qu'aucun fichier ne soit
    borné à l'écriture.

    Unique, et c'est le point : un gain par fichier égaliserait les niveaux et
    effacerait l'indice le plus utile d'une séance ratée — le micro qu'on a
    déplacé entre deux prises. Ici, les écarts sont conservés au décibel près.

    Un lot qui ne dépasse jamais 1,0 n'est pas touché du tout.
    """
    if not cretes:
        return 1.0
    crete_max = max(cretes.values())
    return 1.0 / crete_max if crete_max > 1.0 else 1.0


def prises_trop_fortes(cretes: dict[str, float], seuil: float = 1.05) -> list[str]:
    """Celles dont le dépassement ne s'explique plus par le codec."""
    return sorted(numero for numero, crete in cretes.items() if crete > seuil)


def decoder(chemin: pathlib.Path) -> tuple[np.ndarray, int]:
    """Rend le signal en flottants [-1, 1], mono, et sa fréquence d'origine."""
    with av.open(str(chemin)) as conteneur:
        flux = conteneur.streams.audio[0]
        morceaux = [trame.to_ndarray() for paquet in conteneur.demux(flux) for trame in paquet.decode()]
        frequence = flux.codec_context.sample_rate
    if not morceaux:
        raise ValueError("aucune trame audio décodée")

    signal = np.concatenate([m.reshape(m.shape[0], -1) if m.ndim > 1 else m.reshape(1, -1) for m in morceaux], axis=1)
    if signal.shape[0] > 1:  # plusieurs canaux : moyenne, plutôt que jeter l'un des deux
        signal = signal.mean(axis=0, keepdims=True)
    signal = signal[0].astype(np.float32)

    if np.issubdtype(morceaux[0].dtype, np.integer):
        signal /= float(np.iinfo(morceaux[0].dtype).max)
    return signal, frequence


def ecrire_wav(chemin: pathlib.Path, signal: np.ndarray, frequence: int, gain: float = 1.0) -> None:
    # Le bornage reste, mais en dernier recours seulement : le gain global l'a
    # déjà rendu inutile. S'il agit encore, c'est un signal, pas une routine.
    entiers = np.clip(signal * gain, -1.0, 1.0)
    entiers = (entiers * 32767.0).astype("<i2")
    with wave.open(str(chemin), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(frequence)
        w.writeframes(entiers.tobytes())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--entree", type=pathlib.Path, required=True, help="dossier des notes vocales")
    ap.add_argument("--sortie", type=pathlib.Path, required=True, help="dossier des WAV produits")
    ap.add_argument("--frequence", type=int, default=FREQUENCE_CIBLE, help=f"défaut {FREQUENCE_CIBLE}")
    a = ap.parse_args()

    fichiers = sorted(
        (p for p in a.entree.iterdir() if p.suffix.lower() in EXTENSIONS_SOURCE),
        key=lambda p: (numero_du_nom(p.name) or p.name),
    )
    if not fichiers:
        print(f"Aucune note vocale dans {a.entree}", file=sys.stderr)
        return 2

    a.sortie.mkdir(parents=True, exist_ok=True)
    frequences_source: set[int] = set()
    sans_numero: list[str] = []
    echecs: list[tuple[str, str]] = []
    ecrits = 0
    duree = 0.0

    # PREMIÈRE PASSE — les crêtes seulement. On décode deux fois plutôt que de
    # garder tout un corpus en mémoire : un pod modeste doit y arriver aussi.
    cretes: dict[str, float] = {}
    a_traiter: list[tuple[str, pathlib.Path]] = []
    for chemin in fichiers:
        numero = numero_du_nom(chemin.name)
        if numero is None:
            # Sans numéro, impossible d'apparier avec le script : renommer au
            # hasard serait pire que de laisser la prise de côté.
            sans_numero.append(chemin.name)
            continue
        try:
            signal, frequence = decoder(chemin)
        except Exception as e:  # noqa: BLE001 — un fichier abîmé n'arrête pas les autres
            echecs.append((chemin.name, f"{type(e).__name__}: {e}"))
            continue
        frequences_source.add(frequence)
        cretes[numero] = float(np.abs(signal).max())
        a_traiter.append((numero, chemin))

    if not a_traiter:
        print("Aucun fichier décodable.", file=sys.stderr)
        return 2

    crete_max = max(cretes.values())
    gain = gain_global(cretes)
    trop_fortes = prises_trop_fortes(cretes, CRETE_PLAUSIBLE_CODEC)

    # SECONDE PASSE — l'écriture, avec le même gain pour tous.
    for numero, chemin in a_traiter:
        signal, frequence = decoder(chemin)
        if frequence != a.frequence:
            signal = soxr.resample(signal, frequence, a.frequence, quality="VHQ")
        ecrire_wav(a.sortie / f"{numero}.wav", signal, a.frequence, gain)
        ecrits += 1
        duree += len(signal) / a.frequence

    print(f"{ecrits} fichiers écrits dans {a.sortie}")
    print(f"fréquences d'origine : {sorted(frequences_source)} Hz → {a.frequence} Hz")
    print(f"durée totale : {duree / 60:.1f} min")
    print(f"crête du lot avant gain : {crete_max:.4f} · gain global appliqué : {20 * np.log10(gain):+.2f} dB")
    if trop_fortes:
        print(
            f"\nPRISES TROP FORTES ({len(trop_fortes)}) — au-delà de {CRETE_PLAUSIBLE_CODEC}, "
            "ce n'est plus le codec qui déborde mais l'original qui était écrêté :"
        )
        for numero in trop_fortes:
            print(f"  ! {numero} : crête {cretes[numero]:.3f} — à réenregistrer moins fort")
    if a.frequence > max(frequences_source, default=a.frequence):
        print(
            f"AVERTISSEMENT : suréchantillonnage. Rien n'existe au-dessus de "
            f"{max(frequences_source) // 2} Hz et rien ne le recréera — la voix produite sonnera sourde."
        )
    if sans_numero:
        print(f"\nSANS NUMÉRO ({len(sans_numero)}) — laissés de côté, impossible de les apparier :")
        for nom in sans_numero[:10]:
            print(f"  ✗ {nom}")
    if echecs:
        print(f"\nÉCHECS DE DÉCODAGE ({len(echecs)}) :")
        for nom, motif in echecs[:10]:
            print(f"  ✗ {nom} : {motif}")
    return 1 if (echecs or sans_numero) else 0


if __name__ == "__main__":
    raise SystemExit(main())
