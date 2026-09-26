"""Auto-test de `outils/preparer_corpus_voix.py`, sans réseau ni fichier externe.

Les fichiers audio sont FABRIQUÉS ici, octet par octet : un WAV par le module
`wave`, un flux Ogg/Opus à la main. C'est ce qui permet de vérifier la lecture
d'en-tête sans embarquer d'échantillon dans le dépôt, et sans dépendre d'un
enregistrement réel dont on ne pourrait pas garantir la stabilité.

    python3 outils/tests/test_preparer_corpus_voix.py
"""

import importlib.util
import struct
import sys
import tempfile
import wave
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("pcv", RACINE / "outils" / "preparer_corpus_voix.py")
pcv = importlib.util.module_from_spec(spec)
sys.modules["pcv"] = pcv
spec.loader.exec_module(pcv)

echecs: list[str] = []


def verifier(nom: str, condition: bool, detail: str = "") -> None:
    print(f"  {'OK   ' if condition else 'ECHEC'} {nom} {detail}")
    if not condition:
        echecs.append(nom)


# --- fabrication de fichiers ------------------------------------------------


def page_ogg(granule: int, charge: bytes, sequence: int) -> bytes:
    """Une page Ogg minimale. La somme de contrôle n'est pas calculée : le
    lecteur ne la vérifie pas, et l'inventer ici n'apprendrait rien."""
    table = bytes([255] * (len(charge) // 255) + [len(charge) % 255])
    entete = struct.pack("<4sBBqIIIB", b"OggS", 0, 0, granule, 1, sequence, 0, len(table))
    return entete + table + charge


def fabriquer_opus(chemin: Path, canaux: int, frequence_entree: int, duree_s: float, presaut: int = 312) -> None:
    tete = b"OpusHead" + struct.pack("<BBHIhB", 1, canaux, presaut, frequence_entree, 0, 0)
    granule = int(duree_s * 48000) + presaut  # Opus compte toujours en pas de 48 kHz
    chemin.write_bytes(page_ogg(0, tete, 0) + page_ogg(granule, b"\x00" * 64, 1))


def fabriquer_wav(chemin: Path, frequence: int, duree_s: float, canaux: int = 1) -> None:
    with wave.open(str(chemin), "wb") as w:
        w.setnchannels(canaux)
        w.setsampwidth(2)
        w.setframerate(frequence)
        w.writeframes(b"\x10\x00" * int(frequence * duree_s) * canaux)


# --- le numéro se lit au début du nom, pas ailleurs -------------------------

print("== numéro de prise, lu au début du nom ==")
for nom, attendu in [
    ("0001.wav", "0001"),
    ("001 - WhatsApp Audio 2026-09-25 at 11.07.30.opus", "0001"),
    ("160 - WhatsApp Audio.opus", "0160"),
    ("0000.wav", "0000"),
    ("7.wav", "0007"),
    ("0254 phrase.wav", "0254"),
]:
    verifier(f"« {nom} » → {attendu}", pcv.numero_du_nom(nom) == attendu)

for nom in ["prise-001.wav", "WhatsApp 001.opus", "essai.wav", ""]:
    verifier(f"« {nom} » → rien (le numéro doit OUVRIR le nom)", pcv.numero_du_nom(nom) is None)

verifier("un numéro à cinq chiffres n'est pas tronqué en silence", pcv.numero_du_nom("12345.wav") is None)

# --- regroupement en plages -------------------------------------------------

print("== regroupement des numéros consécutifs ==")
verifier("série continue → une plage", pcv.plages(["0161", "0162", "0163"]) == [("0161", "0163")])
verifier("isolés → autant de plages", pcv.plages(["0005", "0009"]) == [("0005", "0005"), ("0009", "0009")])
verifier("mélange", pcv.plages(["0001", "0002", "0007"]) == [("0001", "0002"), ("0007", "0007")])
verifier("liste vide", pcv.plages([]) == [])

# --- lecture des en-têtes Ogg/Opus -----------------------------------------

print("== en-têtes Ogg/Opus, sans décoder le signal ==")
with tempfile.TemporaryDirectory() as tmp:
    dossier = Path(tmp)

    opus = dossier / "0042 - note vocale.opus"
    fabriquer_opus(opus, canaux=1, frequence_entree=16000, duree_s=4.25)
    m = pcv.mesurer(opus)
    verifier("identifiant déduit du nom", m.identifiant == "0042", f"→ {m.identifiant}")
    verifier("format reconnu", m.format == "opus")
    verifier("canaux lus", m.canaux == 1)
    verifier("fréquence FOURNIE À L'ENCODEUR lue", m.frequence == 16000, f"→ {m.frequence}")
    verifier("durée calculée depuis la granule 48 kHz", abs(m.duree - 4.25) < 0.001, f"→ {m.duree:.3f} s")
    verifier("signal déclaré NON lisible", m.signal_lisible is False)
    verifier("débit calculé", m.debit_kbps is not None and m.debit_kbps > 0)

    stereo = dossier / "0043 - stereo.opus"
    fabriquer_opus(stereo, canaux=2, frequence_entree=48000, duree_s=2.0)
    m2 = pcv.mesurer(stereo)
    verifier("stéréo détectée", m2.canaux == 2)
    verifier("48 kHz déclaré lu tel quel", m2.frequence == 48000)

    # --- non-régression : le WAV se lit toujours comme avant
    print("== non-régression WAV ==")
    w = dossier / "0001.wav"
    fabriquer_wav(w, frequence=22050, duree_s=1.5)
    mw = pcv.mesurer(w)
    verifier("format wav", mw.format == "wav")
    verifier("signal lisible", mw.signal_lisible is True)
    verifier("fréquence", mw.frequence == 22050)
    verifier("durée", abs(mw.duree - 1.5) < 0.01, f"→ {mw.duree:.3f} s")
    verifier("échantillons accessibles", mw.echantillons is not None and len(mw.echantillons) > 0)

    # --- le verdict sur un lot compressé
    print("== verdict sur un lot compressé ==")
    phrases = {"0042": "une phrase", "0043": "une autre"}
    problemes = pcv.verifier([pcv.mesurer(opus), pcv.mesurer(stereo)], phrases, None)
    messages = [p.message for p in problemes]
    verifier(
        "la compression avec perte est signalée UNE fois",
        sum("compressés avec perte" in x for x in messages) == 1,
    )
    verifier(
        "la fréquence insuffisante est signalée",
        any("16000 Hz" in x for x in messages),
    )
    verifier("la stéréo est signalée", any("2 canaux" in x for x in messages))
    verifier(
        "AUCUNE alerte de niveau sur un fichier non décodé",
        not any("niveau" in x for x in messages),
        "(un -120 dB par défaut aurait menti)",
    )
    verifier(
        "AUCUNE alerte de saturation sur un fichier non décodé",
        not any("saturation" in x for x in messages),
    )
    verifier("l'absence de prise de bruit est signalée", any("bruit de fond absente" in x for x in messages))

# --- gain global du décodeur de rattrapage ---------------------------------
# Importé ici plutôt que dans son propre fichier : ces deux fonctions sont
# pures, et un test qui exige `av` installé ne tournerait pas sur un pod nu.

print("== gain global (décodeur de rattrapage) ==")
_spec_d = importlib.util.spec_from_file_location("dnv_src", RACINE / "outils" / "decoder_notes_vocales.py")
_src = _spec_d.origin
_code = Path(_src).read_text(encoding="utf-8")
_ns: dict = {"np": None}
# On n'exécute QUE les deux fonctions pures, sans importer av ni soxr.
_debut = _code.index("def gain_global(")
_fin = _code.index("def decoder(")
exec(compile(_code[_debut:_fin], _src, "exec"), _ns)  # noqa: S102
gain_global = _ns["gain_global"]
prises_trop_fortes = _ns["prises_trop_fortes"]

verifier("lot sous 1,0 : aucun gain appliqué", gain_global({"0001": 0.8, "0002": 0.95}) == 1.0)
verifier("lot vide : aucun gain", gain_global({}) == 1.0)
verifier(
    "le gain ramène la crête la plus haute à 1,0 exactement",
    abs(gain_global({"0001": 0.5, "0002": 1.415}) * 1.415 - 1.0) < 1e-9,
)
_g = gain_global({"0001": 0.50, "0002": 1.20})
verifier(
    "les écarts de niveau entre prises sont PRÉSERVÉS (pas de normalisation par fichier)",
    abs((0.50 * _g) / (1.20 * _g) - 0.50 / 1.20) < 1e-9,
    "(sinon on effacerait l'indice d'un micro déplacé)",
)
verifier(
    "au-delà du seuil, la prise est nommée — le codec n'explique plus",
    prises_trop_fortes({"0011": 1.0046, "0107": 1.2894, "0109": 1.4150}) == ["0107", "0109"],
)
verifier(
    "le dépassement ordinaire du codec n'accuse personne",
    prises_trop_fortes({"0011": 1.0046, "0028": 1.0040}) == [],
)

print()
if echecs:
    print(f"{len(echecs)} test(s) en échec : {', '.join(echecs)}")
    raise SystemExit(1)
print("Tous les tests passent.")
