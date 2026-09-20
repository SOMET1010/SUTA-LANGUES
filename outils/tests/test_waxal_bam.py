"""Auto-test de `outils/waxal_bam.py`, sans réseau.

Ce script tournera sur un pod, loin de tout confort de débogage. Les deux
fonctions pures qu'il contient — lecture d'en-tête audio et détection du biais
liturgique — sont donc vérifiées ICI, avant le départ.

    python3 outils/tests/test_waxal_bam.py
"""

import importlib.util
import re
import struct
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("waxal_bam", RACINE / "outils" / "waxal_bam.py")
wb = importlib.util.module_from_spec(spec)
sys.modules["waxal_bam"] = wb
spec.loader.exec_module(wb)

echecs: list[str] = []


def verifier(nom: str, condition: bool, detail: str = "") -> None:
    print(f"  {'OK   ' if condition else 'ECHEC'} {nom} {detail}")
    if not condition:
        echecs.append(nom)


def entete_wav(secondes: float, taux: int = 16000, canaux: int = 1, bits: int = 16) -> bytes:
    octets = int(taux * canaux * bits / 8 * secondes)
    fmt = struct.pack("<HHIIHH", 1, canaux, taux, taux * canaux * bits // 8, canaux * bits // 8, bits)
    return (
        b"RIFF" + struct.pack("<I", 36 + octets) + b"WAVE"
        + b"fmt " + struct.pack("<I", 16) + fmt
        + b"data" + struct.pack("<I", octets)
    )


def entete_flac(echantillons: int, taux: int) -> bytes:
    info = bytearray(34)
    info[10] = (taux >> 12) & 0xFF
    info[11] = (taux >> 4) & 0xFF
    info[12] = (taux & 0x0F) << 4
    info[13] = (echantillons >> 32) & 0x0F
    info[14:18] = (echantillons & 0xFFFFFFFF).to_bytes(4, "big")
    return b"fLaC" + b"\x00\x00\x00\x22" + bytes(info)


print("== durée lue dans l'en-tête, sans décoder le signal ==")
for secondes in (0.5, 3.0, 12.75):
    d = wb._duree_entete_audio(entete_wav(secondes))
    verifier(f"WAV {secondes} s", d is not None and abs(d - secondes) < 0.001, f"→ {d}")
verifier("WAV 48 kHz stéréo 24 bits",
         abs((wb._duree_entete_audio(entete_wav(2.0, 48000, 2, 24)) or 0) - 2.0) < 0.001)
for ech, taux, attendu in ((48000, 48000, 1.0), (22050, 22050, 1.0), (960000, 16000, 60.0)):
    d = wb._duree_entete_audio(entete_flac(ech, taux))
    verifier(f"FLAC {attendu} s", d is not None and abs(d - attendu) < 0.01, f"→ {d}")

print("== un format non géré rend None, jamais une estimation inventée ==")
verifier("MP3", wb._duree_entete_audio(b"\xff\xfb" + b"\x00" * 200) is None)
verifier("OGG", wb._duree_entete_audio(b"OggS" + b"\x00" * 200) is None)
verifier("trop court", wb._duree_entete_audio(b"ab") is None)
verifier("vide", wb._duree_entete_audio(b"") is None)

print("== normalisation des lettres ouest-africaines (NFD ne suffit pas) ==")
for brut, attendu in (("DƆNKILI", "donkili"), ("EDWƐNE", "edwene"),
                      ("ɲɔgɔn", "nyogon"), ("Téléphone", "telephone")):
    verifier(f"« {brut} »", wb._norm(brut) == attendu, f"→ {wb._norm(brut)}")

print("== biais liturgique, sur les citations RÉELLES relevées dans l'audit ==")
motifs = [re.compile(p) for p in wb.MARQUEURS_LITURGIQUES]


def liturgique(texte: str) -> bool:
    return any(p.search(wb._norm(texte)) for p in motifs)


CAS = [
    # Relevés dans african-speech-ipa, configs jula_dyu et nzema_nzi.
    ("Gyihova Baboa Wɔ Yeamaa Wɔagyinla", True),
    ("EDWƐNE 44 Anwunvɔnenli Asɔneyɛlɛ", True),
    ("na yɛze kɛ ( Wlo. 8:35-39 ) Baebolo nu ngyinlazo", True),
    ("DƆNKILI 134", True),
    # « EDWƐKƐ 17 » est l'un des titres mal alignés relevés dans nzema_nzi
    # pendant l'audit — deux mots pour 9,85 s d'audio. Il DOIT être signalé :
    # c'est du Watchtower, même sans nom propre biblique.
    ("EDWƐKƐ 17", True),
    # Parole ordinaire : aucun marqueur ne doit se déclencher.
    ("I ni ce, i ka kɛnɛ wa ?", False),
    ("N b'a fɛ ka telefɔni san", False),
    ("Muso ye sugu la", False),
    ("Mankan bonya dɔɔnin", False),
]
for texte, attendu in CAS:
    verifier(f"« {texte[:40]} »", liturgique(texte) == attendu, f"attendu={attendu}")

print("== rendu du rapport ==")
m = wb.Mesure(
    fichiers=26, octets=5_079_435_336,
    lignes_par_split={"train": 1600, "validation": 218, "test": 192},
    colonnes=["audio", "text", "speaker_id", "duration"],
    heures_audio=12.5, methode_duree="somme exacte",
    locuteurs_distincts=1, echantillons_texte=["I ni ce"],
    liturgique_sur=0, liturgique_total=400,
    alertes=["Un seul locuteur : cohérent avec un volet TTS studio."],
)
r = wb.rendre_rapport(m)
verifier("rapport non vide", len(r) > 600, f"({len(r)} caractères)")
verifier("porte les heures", "12.5 h" in r)
verifier("avertit sur la licence", "CC-BY-SA-4.0" in r)
verifier("porte le total de lignes", "2,010" in r)
verifier("porte la section des limites", "ne dit PAS" in r)

vide = wb.rendre_rapport(wb.Mesure())
verifier("rapport dégradé sans mesure", "non mesurées" in vide)

print(f"\n{'ÉCHECS : ' + ', '.join(echecs) if echecs else 'Tous les tests passent.'}")
sys.exit(1 if echecs else 0)
