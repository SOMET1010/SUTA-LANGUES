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

IL LIT AUSSI L'OPUS, MAIS SEULEMENT POUR LE RECALER
---------------------------------------------------
Les premières prises arrivent souvent en notes vocales (WhatsApp, Telegram),
c'est-à-dire en Opus très compressé. Refuser ces fichiers en bloc, sans rien
dire, laisserait croire que la séance est perdue — alors que la numérotation,
les durées et la régularité du débit y sont peut-être excellentes, et que c'est
la matière du CASTING.

L'outil les mesure donc, à partir des en-têtes Ogg/Opus, sans décoder le
signal : aucune bibliothèque tierce, l'outil doit tourner sur un pod nu. Ce
qui se lit ainsi : canaux, durée, fréquence fournie à l'encodeur, débit. Ce qui
ne se lit PAS : niveau, saturation, silences de bords. Le rapport le dit au
lieu de laisser croire à une mesure complète.

Un fichier compressé avec perte reste BLOQUANT pour l'entraînement, et la
construction du jeu de données le refuse même avec --forcer : produire un
dataset invalide serait pire que de ne rien produire.

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
import struct
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
EXTENSIONS = (".wav", ".opus", ".ogg")


def numero_du_nom(nom: str) -> str | None:
    """
    Le numéro de prise, lu au début du nom de fichier et ramené à quatre
    chiffres.

    On ne peut pas se contenter du nom complet : un enregistreur de téléphone
    produit « 001 - WhatsApp Audio 2026-09-25 at 11.07.30.opus », jamais
    « 0001.wav ». Exiger la seconde forme ferait échouer l'appariement sur des
    fichiers parfaitement numérotés par la personne qui a enregistré — on
    l'accuserait d'une faute qu'elle n'a pas commise.

    Ce qui est exigé, en revanche : que le numéro OUVRE le nom. Un numéro noyé
    au milieu serait une devinette, et on ne devine pas sur un corpus.
    """
    m = re.match(r"^(\d{1,4})(?!\d)", nom)
    return m.group(1).zfill(4) if m else None


class Probleme:
    BLOQUANT = "bloquant"
    ALERTE = "alerte"

    def __init__(self, gravite: str, fichier: str, message: str) -> None:
        self.gravite, self.fichier, self.message = gravite, fichier, message

    def __str__(self) -> str:
        marque = "✗" if self.gravite == Probleme.BLOQUANT else "!"
        return f"  {marque} {self.fichier:>8}  {self.message}"


class Mesure:
    """
    Une prise, mesurée.

    `signal_lisible` dit si le signal lui-même a pu être examiné. Faux pour un
    fichier compressé : les contrôles de niveau, de saturation et de silence
    sont alors SAUTÉS, pas réputés bons. Un -120 dB par défaut ferait croire à
    un fichier muet et déclencherait une alerte mensongère.
    """

    format = "wav"
    signal_lisible = True
    debit_kbps: float | None = None

    def __init__(self, chemin: pathlib.Path) -> None:
        self.chemin = chemin
        self.identifiant = numero_du_nom(chemin.name) or chemin.stem
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


class MesureOpus:
    """
    Une prise en Ogg/Opus, mesurée par ses en-têtes.

    POURQUOI PAS DE DÉCODAGE
    ------------------------
    La bibliothèque standard ne décode pas l'Opus, et cet outil doit tourner
    sur un pod nu, sans rien installer. On lit donc la structure du conteneur
    Ogg, qui suffit à répondre aux questions qui décident :

    - `OpusHead` donne le nombre de canaux et la FRÉQUENCE FOURNIE À
      L'ENCODEUR. C'est le chiffre qui compte : 16 000 Hz signifie que rien
      n'existe au-dessus de 8 kHz, et aucun rééchantillonnage ne le recréera.
    - La dernière position granulaire donne la durée exacte, en pas de
      48 kHz — l'horloge interne d'Opus, indépendante de la source.
    - La taille du fichier rapportée à la durée donne le débit, donc le degré
      de compression.

    Ce qui reste hors de portée — niveau, saturation, silences — est déclaré
    non mesuré, jamais supposé bon.
    """

    format = "opus"
    signal_lisible = False
    echantillons = None

    def __init__(self, chemin: pathlib.Path) -> None:
        self.chemin = chemin
        self.identifiant = numero_du_nom(chemin.name) or chemin.stem
        donnees = chemin.read_bytes()

        entete = None
        derniere_granule = 0
        for granule, charge in self._pages(donnees):
            if entete is None and charge.startswith(b"OpusHead"):
                # <BBHIhB : version, canaux, pré-saut, fréquence d'entrée,
                #           gain de sortie, famille de mappage
                _, canaux, presaut, frequence_entree, _, _ = struct.unpack_from("<BBHIhB", charge, 8)
                entete = (canaux, presaut, frequence_entree)
            if granule > 0:
                derniere_granule = granule

        if entete is None:
            raise ValueError("flux Opus sans en-tête OpusHead")

        self.canaux, presaut, self.frequence = entete
        # Opus compte toujours en pas de 48 kHz, quelle que soit la source.
        self.duree = max(0.0, (derniere_granule - presaut) / 48000.0)
        self.largeur = LARGEUR_ATTENDUE  # sans objet ici : le contrôle est sauté
        self.octets = len(donnees)
        self.debit_kbps = (self.octets * 8 / self.duree / 1000) if self.duree > 0 else None

    @staticmethod
    def _pages(donnees: bytes):
        """Parcourt les pages Ogg, en rendant (position granulaire, charge)."""
        i = 0
        while True:
            i = donnees.find(b"OggS", i)
            if i < 0 or i + 27 > len(donnees):
                return
            _, _, _, granule, _, _, _, nb_segments = struct.unpack_from("<4sBBqIIIB", donnees, i)
            if i + 27 + nb_segments > len(donnees):
                return
            table = donnees[i + 27 : i + 27 + nb_segments]
            debut = i + 27 + nb_segments
            yield granule, donnees[debut : debut + sum(table)]
            i = debut + sum(table)

    # Les mesures de signal n'existent pas ici. On rend des valeurs neutres,
    # mais `signal_lisible = False` fait que personne ne les regarde.
    crete = 0.0
    satures = 0
    rms_db = 0.0
    silence_tete = 0.0
    silence_queue = 0.0


def mesurer(chemin: pathlib.Path) -> Mesure | MesureOpus:
    """Choisit la bonne lecture selon l'extension."""
    if chemin.suffix.lower() in (".opus", ".ogg"):
        return MesureOpus(chemin)
    return Mesure(chemin)


def lire_script(chemin: pathlib.Path) -> dict[str, str]:
    """Les phrases numérotées du script, indexées par leur numéro à quatre chiffres."""
    phrases: dict[str, str] = {}
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^(\d{4})\s\s+(.+?)\s*$", ligne)
        if m:
            phrases[m.group(1)] = m.group(2)
    return phrases


def plages(identifiants: list[str]) -> list[tuple[str, str]]:
    """Regroupe des numéros consécutifs en (premier, dernier)."""
    resultat: list[tuple[str, str]] = []
    for ident in identifiants:
        if resultat and int(ident) == int(resultat[-1][1]) + 1:
            resultat[-1] = (resultat[-1][0], ident)
        else:
            resultat.append((ident, ident))
    return resultat


def verifier(mesures: list[Mesure], phrases: dict[str, str], bruit: Mesure | None) -> list[Probleme]:
    problemes: list[Probleme] = []
    par_id = {m.identifiant: m for m in mesures}

    # 1. La correspondance audio/texte — le défaut qui ruine tout le reste.
    manquants = sorted(set(phrases) - set(par_id))
    orphelins = sorted(set(par_id) - set(phrases))
    # Une séance interrompue laisse des dizaines d'absences consécutives.
    # Les lister une par une noierait les VRAIS défauts — ceux qui sont
    # isolés, et donc suspects. On rend des plages.
    for debut, fin in plages(manquants):
        etendue = debut if debut == fin else f"{debut}–{fin}"
        nombre = "" if debut == fin else f" ({int(fin) - int(debut) + 1} phrases)"
        problemes.append(Probleme(Probleme.BLOQUANT, etendue, f"script sans enregistrement{nombre}"))
    for debut, fin in plages(orphelins):
        etendue = debut if debut == fin else f"{debut}–{fin}"
        problemes.append(Probleme(Probleme.BLOQUANT, etendue, "enregistrement sans phrase correspondante"))

    # 2. Le format doit être IDENTIQUE partout : Piper entraîne à une seule
    #    fréquence, et un fichier qui détonne contamine tout le lot.
    frequences = {m.frequence for m in mesures}
    if len(frequences) > 1:
        problemes.append(Probleme(Probleme.BLOQUANT, "—", f"fréquences mélangées : {sorted(frequences)}"))

    # 2bis. La compression avec perte, signalée UNE fois pour tout le lot :
    #       répéter le même reproche 160 fois n'apprend rien de plus.
    compresses = [m for m in mesures if m.format != "wav"]
    if compresses:
        debits = [m.debit_kbps for m in compresses if m.debit_kbps]
        moyen = f", ~{sum(debits) / len(debits):.0f} kbit/s" if debits else ""
        problemes.append(
            Probleme(
                Probleme.BLOQUANT,
                "—",
                f"{len(compresses)} fichiers compressés avec perte{moyen} : "
                "utilisables pour le casting, pas pour entraîner",
            )
        )

    # 2ter. Les défauts de FORMAT sont presque toujours collectifs : un
    #       réglage d'enregistreur vaut pour toute la séance. Les énumérer
    #       fichier par fichier remplirait l'écran d'une même phrase et
    #       enterrerait les défauts isolés, qui sont les intéressants.
    for defaut, valeur in (
        ("frequence", lambda m: f"{m.frequence} Hz — minimum {FREQUENCE_MIN}" if m.frequence < FREQUENCE_MIN else None),
        ("canaux", lambda m: f"{m.canaux} canaux — mono attendu" if m.canaux != CANAUX_ATTENDUS else None),
        (
            "largeur",
            lambda m: f"{m.largeur * 8} bits — 16 attendus"
            if m.signal_lisible and m.largeur != LARGEUR_ATTENDUE
            else None,
        ),
    ):
        groupes: dict[str, list[str]] = {}
        for m in mesures:
            message = valeur(m)
            if message:
                groupes.setdefault(message, []).append(m.identifiant)
        for message, identifiants in groupes.items():
            if len(identifiants) == 1:
                problemes.append(Probleme(Probleme.BLOQUANT, identifiants[0], message))
            elif len(identifiants) == len(mesures):
                problemes.append(Probleme(Probleme.BLOQUANT, "tous", message))
            else:
                etendues = ", ".join(d if d == f else f"{d}–{f}" for d, f in plages(sorted(identifiants)))
                problemes.append(
                    Probleme(Probleme.BLOQUANT, f"{len(identifiants)} fich.", f"{message} — {etendues}")
                )

    for m in mesures:
        if m.duree < DUREE_MIN:
            problemes.append(Probleme(Probleme.BLOQUANT, m.identifiant, f"{m.duree:.2f} s — phrase tronquée ?"))
        elif m.duree > DUREE_MAX:
            problemes.append(Probleme(Probleme.ALERTE, m.identifiant, f"{m.duree:.1f} s — deux phrases en un fichier ?"))
        if not m.signal_lisible:
            continue  # niveau, saturation et silences : non mesurés, pas « bons »
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
    niveaux = sorted(m.rms_db for m in mesures if m.signal_lisible and m.echantillons)
    if niveaux:
        median = niveaux[len(niveaux) // 2]
        for m in mesures:
            if not m.signal_lisible:
                continue
            ecart = m.rms_db - median
            if abs(ecart) > ECART_NIVEAU_DB:
                problemes.append(
                    Probleme(Probleme.ALERTE, m.identifiant, f"niveau {ecart:+.1f} dB du médian — micro déplacé ?")
                )

    # 4. Le bruit de fond, mesuré sur la prise de silence.
    if bruit is None:
        problemes.append(Probleme(Probleme.ALERTE, FICHIER_SILENCE, "prise de bruit de fond absente"))
    elif not bruit.signal_lisible:
        problemes.append(
            Probleme(Probleme.ALERTE, FICHIER_SILENCE, "prise de bruit compressée : bruit de fond non mesurable")
        )
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
    ap.add_argument("--audio", type=pathlib.Path, required=True, help="dossier des enregistrements bruts")
    ap.add_argument("--script", type=pathlib.Path, required=True, help="script d'enregistrement numéroté")
    ap.add_argument("--sortie", type=pathlib.Path, default=None, help="jeu de données à construire")
    ap.add_argument(
        "--forcer",
        action="store_true",
        help="construire malgré les bloquants (sans effet sur les fichiers compressés)",
    )
    a = ap.parse_args()

    phrases = lire_script(a.script)
    if not phrases:
        print(f"Aucune phrase numérotée trouvée dans {a.script}", file=sys.stderr)
        return 2

    fichiers = sorted(
        (p for p in a.audio.iterdir() if p.suffix.lower() in EXTENSIONS),
        key=lambda p: (numero_du_nom(p.name) or p.name),
    )
    if not fichiers:
        print(f"Aucun enregistrement ({', '.join(EXTENSIONS)}) dans {a.audio}", file=sys.stderr)
        return 2

    mesures, bruit = [], None
    illisibles = []
    for chemin in fichiers:
        try:
            m = mesurer(chemin)
        except (wave.Error, EOFError, ValueError, struct.error) as e:
            # Un fichier illisible n'arrête plus tout : on le signale et on
            # continue. Sinon une seule prise corrompue priverait la personne
            # du rapport sur les 159 autres.
            illisibles.append((chemin.name, str(e)))
            continue
        if m.identifiant == FICHIER_SILENCE:
            bruit = m
        else:
            mesures.append(m)

    if illisibles:
        print(f"ILLISIBLES ({len(illisibles)}) — ignorés dans la suite")
        for nom, motif in illisibles:
            print(f"  ✗ {nom} : {motif}")
        print()
    if not mesures:
        print("Aucun enregistrement exploitable.", file=sys.stderr)
        return 2

    problemes = verifier(mesures, phrases, bruit)
    bloquants = [p for p in problemes if p.gravite == Probleme.BLOQUANT]
    alertes = [p for p in problemes if p.gravite == Probleme.ALERTE]

    duree_totale = sum(m.duree for m in mesures)
    formats: dict[str, int] = {}
    for m in mesures:
        formats[m.format] = formats.get(m.format, 0) + 1
    print(f"{len(mesures)} enregistrements · {len(phrases)} phrases au script")
    print("formats : " + " · ".join(f"{n} × {f}" for f, n in sorted(formats.items())))
    print(f"fréquences : {sorted({m.frequence for m in mesures})} Hz")
    print(f"durée utile : {duree_totale / 60:.1f} min · moyenne {duree_totale / max(len(mesures), 1):.1f} s")
    debits = [m.debit_kbps for m in mesures if m.debit_kbps]
    if debits:
        print(f"débit moyen des fichiers compressés : {sum(debits) / len(debits):.0f} kbit/s")
    if bruit and bruit.signal_lisible:
        print(f"bruit de fond : {bruit.rms_db:.0f} dB")
    non_mesures = [m for m in mesures if not m.signal_lisible]
    if non_mesures:
        print(
            f"NON MESURÉS sur {len(non_mesures)} fichiers : niveau, saturation, silences de bords "
            "(format compressé — non décodé, donc non supposé bon)"
        )
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
    if non_mesures:
        # Non négociable, --forcer compris : copier un .opus en le nommant
        # .wav produirait un jeu de données faux, découvert des heures de GPU
        # plus tard. Mieux vaut ne rien produire.
        print(
            f"Construction refusée : {len(non_mesures)} fichiers compressés avec perte. "
            "Réenregistrez sans passer par une messagerie — --forcer ne s'applique pas ici.",
            file=sys.stderr,
        )
        return 1
    if bloquants and not a.forcer:
        print("Construction refusée : corrigez les bloquants, ou passez --forcer.", file=sys.stderr)
        return 1

    n = construire(mesures, phrases, a.sortie)
    print(f"Jeu de données écrit : {a.sortie} — {n} paires audio/texte")
    print(f"Fréquence à passer à Piper : {mesures[0].frequence}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
