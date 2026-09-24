#!/usr/bin/env python3
"""
Script d'enregistrement pour la voix native de SUTA.

POURQUOI IL EST GÉNÉRÉ ET NON ÉCRIT À LA MAIN
---------------------------------------------
Une voix de synthèse ne prononce bien que ce qu'elle a entendu. Les voix
françaises d'Azure — métropolitaine, canadienne, belge, suisse — n'ont jamais
entendu Nambékaha, N'Guessankro ni Bogodougou : elles les déforment, et c'est
la première chose qu'un Ivoirien remarque.

Le corpus de SUTA contient plus de 15 000 libellés de localités. Ce générateur
y puise les toponymes RÉELS que l'assistant devra prononcer, en équilibrant les
familles morphologiques qui font trébucher une voix française :

    -kro      Akakro, Kouassikro, Yobouékro…   (le plus fréquent)
    -kaha     Nambékaha, Sékonkaha, Dokaha…    (nord, sénoufo)
    -dougou   Bogodougou, Sékodougou…          (nord, mandingue)
    -koro     Farakoro, Linguékoro…
    N'…       N'Guessankro, N'Dakro, N'Denou…  (apostrophe initiale)

Les écrire à la main, c'est en choisir trente au hasard. Les tirer du corpus,
c'est couvrir ce que SUTA rencontre vraiment.

USAGE
-----
    python3 outils/generer_script_voix.py \
        --fiches ../SUTA-BOT/supabase/fiches \
        --sortie voix/script-enregistrement-fr.txt

Sans --fiches, le générateur utilise la liste de secours embarquée ci-dessous
(relevée le 24/09/2026) : le script reste reproductible même hors du dépôt
SUTA-BOT.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import random
import re
import unicodedata

GRAINE = 20260924  # reproductible : même graine, même script

# Relevés dans supabase/fiches le 24/09/2026, en cas d'absence du corpus.
SECOURS = [
    "Akakro", "N'Guessankro", "Koffikro", "Kongodjan", "Yaokro", "Kouamekro",
    "Allokokro", "Golikro", "N'Dakro", "Linguekoro", "Kouassikro", "Bogodougou",
    "Babadougou", "Assouakro", "N'Drikro", "Assamoikro", "Bondoukou", "Totokro",
    "Farakoro", "Sokouraba", "Assekro", "Bouakro", "Kongokro", "Adjekro",
    "Allakro", "Kouakro", "Kouadiokro", "Seguebe", "Dokaha", "Nambekaha",
    "Sekonkaha", "Adoukro", "Bonikro", "N'Denou", "Amanikro", "Sekodougou",
    "Banangoro", "Katiali", "Agbakro", "Kouakoukro", "Takikro", "Yobouekro",
    "Konankro", "Korhogo", "Sinematiali", "Jacqueville", "Yamoussoukro",
    "Soubre", "Lakota", "Songon", "Yopougon", "Bouake", "Daloa", "Man",
]

FAMILLES = [
    ("kro", r"kro$"),
    ("kaha", r"kaha$"),
    ("dougou", r"dougou$"),
    ("koro", r"koro$"),
    ("apostrophe", r"^[A-Z]'"),
]


def sans_accents(texte: str) -> str:
    d = unicodedata.normalize("NFD", texte)
    return "".join(c for c in d if unicodedata.category(c) != "Mn")


def charger_toponymes(dossier: pathlib.Path | None) -> list[str]:
    if dossier is None or not dossier.is_dir():
        return list(SECOURS)
    trouves: set[str] = set()
    clefs = {"localite", "localité", "nom", "ville", "commune", "titre", "title"}

    def visiter(noeud) -> None:
        if isinstance(noeud, dict):
            for clef, valeur in noeud.items():
                if clef.lower() in clefs and isinstance(valeur, str):
                    m = re.match(r"^(?:Localité|Opérateurs mobiles)\s*—\s*(.+)$", valeur)
                    nom = (m.group(1) if m else valeur).strip()
                    if 3 <= len(nom) <= 24 and not nom[0].isdigit() and " " not in nom.strip():
                        trouves.add(nom)
                visiter(valeur)
        elif isinstance(noeud, list):
            for valeur in noeud:
                visiter(valeur)

    for fichier in sorted(dossier.glob("*.json")):
        try:
            visiter(json.loads(fichier.read_text(encoding="utf-8")))
        except Exception:  # noqa: BLE001 — un fichier illisible ne doit pas tout arrêter
            continue
    return sorted(trouves) or list(SECOURS)


def repartir(toponymes: list[str], par_famille: int, alea: random.Random) -> list[str]:
    """Tire des noms en couvrant chaque famille morphologique, sans doublon."""
    choisis: list[str] = []
    pris: set[str] = set()
    for _, motif in FAMILLES:
        candidats = [t for t in toponymes if re.search(motif, sans_accents(t)) and t not in pris]
        alea.shuffle(candidats)
        for nom in candidats[:par_famille]:
            choisis.append(nom)
            pris.add(nom)
    reste = [t for t in toponymes if t not in pris]
    alea.shuffle(reste)
    for nom in reste[: par_famille * 2]:
        choisis.append(nom)
        pris.add(nom)
    alea.shuffle(choisis)
    return choisis


# --- Les phrases -----------------------------------------------------------

AMORCE = [
    "Bonjour, je suis SUTA, l'assistant de l'ANSUT.",
    "Dites-moi le nom de votre village et je regarde avec vous.",
    "On est ensemble.",
    "Je vous écoute.",
    "Par quoi voulez-vous commencer ?",
    "Je peux vous dire si votre localité est connectée.",
    "Je peux vous indiquer les opérateurs présents chez vous.",
    "Je peux vous orienter vers une formation au numérique.",
    "Je ne trouve pas cette information dans mes documents.",
    "Je préfère vous le dire franchement : je ne sais pas.",
    "Voulez-vous que je cherche autrement ?",
    "C'est noté.",
    "Un instant, je regarde.",
    "Je cherche dans les fiches de l'ANSUT.",
    "Voilà ce que je trouve.",
    "Je n'ai pas bien entendu, pouvez-vous répéter ?",
    "Reprenons depuis le début.",
    "Est-ce que cela répond à votre question ?",
    "Avez-vous besoin d'autre chose ?",
    "Merci, et à bientôt.",
]

GABARITS_LIEU = [
    "{lieu} est couvert par le réseau mobile.",
    "À {lieu}, la fibre optique n'est pas encore arrivée.",
    "Je regarde la situation de {lieu}.",
    "{lieu} se trouve dans le département voisin.",
    "Voulez-vous parler de {lieu} ou d'une autre localité ?",
    "La couverture de {lieu} a été relevée en mai.",
    "Deux opérateurs sont présents à {lieu}.",
    "Il n'y a pas d'antenne à {lieu} pour le moment.",
    "{lieu} compte un point connecté.",
    "Le signalement concerne {lieu}.",
    "Entre {lieu} et {autre}, il y a une vingtaine de kilomètres.",
    "Parlez-vous de {lieu} ou de {autre} ?",
    "{lieu} et {autre} dépendent du même département.",
]

VOCABULAIRE = [
    "La fibre optique relie les chefs-lieux de région.",
    "La couverture mobile n'est pas la même que la couverture Internet.",
    "Une zone blanche est une zone sans aucun réseau.",
    "Le débit descendant se mesure en mégabits par seconde.",
    "Orange, MTN et Moov sont les trois opérateurs mobiles du pays.",
    "L'ANSUT est l'Agence nationale du service universel des télécommunications.",
    "Le PND est le Plan national de développement.",
    "Le PTBA est le plan de travail et de budget annuel.",
    "Le PASS permet de s'équiper d'un smartphone subventionné.",
    "L'ARTCI régule les télécommunications en Côte d'Ivoire.",
    "Le RGPH est le recensement général de la population et de l'habitat.",
    "La DRENA est la direction régionale de l'éducation nationale.",
    "ANSUT CONNECTE rapproche le numérique des populations.",
    "Une école électrifiée peut accueillir une salle informatique.",
    "Le service universel concerne les zones que le marché ne dessert pas.",
    "Un point connecté offre un accès public à Internet.",
    "La littératie numérique, c'est savoir se servir des outils.",
    "L'inclusion numérique vise celles et ceux qui restent à l'écart.",
    "Le signalement remonte directement aux équipes de l'ANSUT.",
    "Le maillage du territoire progresse chaque année.",
]

CHIFFRES = [
    "Quatre-vingt-douze pour cent de la population est couverte.",
    "Le débit atteint vingt-trois mégabits par seconde.",
    "Trois mille deux cent quarante localités sont recensées.",
    "La mesure date du quinze mai deux mille vingt-six.",
    "Il reste dix-sept kilomètres de fibre à poser.",
    "Le relevé porte sur vingt-six mille cent douze fiches.",
    "Sur mille écoles, une seule est électrifiée.",
    "Le taux passe de soixante-huit à soixante-quatorze pour cent.",
    "Le projet court de deux mille vingt-six à deux mille trente.",
    "Comptez entre cinq et huit jours ouvrables.",
    "Le premier trimestre s'achève le trente et un mars.",
    "Deux cent quatre-vingts villages sont concernés.",
    "Le coût est estimé à quinze millions de francs CFA.",
    "Neuf heures du matin, heure d'Abidjan.",
    "La couverture est de cent pour cent sur ce département.",
]

# Couverture phonétique du français : nasales, /ɥ/, /ʁ/ en toutes positions,
# liaisons, groupes consonantiques, voyelles ouvertes et fermées.
PHONETIQUE = [
    "Le vent du nord souffle sur les champs de coton.",
    "Huit huîtres cuites huilent le pinceau du peintre.",
    "Quinze grands bancs brillent sous un ciel brun.",
    "La grenouille grimpe le long du grillage rouillé.",
    "Un bon vin blanc vaut bien un long banquet.",
    "Ce soir, je serai chez toi avant sept heures.",
    "Les enfants jouent dehors pendant que l'orage gronde.",
    "Il faut qu'il aille voir ailleurs si j'y suis.",
    "Trois très gros rats gris traversent la route.",
    "Mon oncle Aimé emmène Anne en ville.",
    "Le pneu crevé siffle doucement dans le silence.",
    "Elle a choisi la chaise chez le charpentier.",
    "Georges juge que le jury jugera justement.",
    "Une pluie fine tombe sur le toit de tôle.",
    "Nous nous approchons lentement du village endormi.",
    "L'ingénieur installe une antenne au sommet de la colline.",
    "Personne n'ignore que le progrès prend du temps.",
    "Quatre-vingts kilomètres séparent les deux communes.",
    "Le chef du quartier accueille les visiteurs avec le sourire.",
    "Tout le monde attend que la lumière revienne.",
    "Ce petit pont de bois enjambe un ruisseau tranquille.",
    "Je n'ai jamais entendu une histoire aussi extraordinaire.",
    "Sa famille habite près de la gare depuis longtemps.",
    "Les travaux commenceront dès que le budget sera voté.",
    "Un yaourt, une bouteille d'huile et deux boîtes d'allumettes.",
]

PROSODIE = [
    "Votre village est-il connecté ?",
    "Quels opérateurs couvrent votre localité ?",
    "Où puis-je me former au numérique ?",
    "Comment puis-je m'équiper ?",
    "Vous voulez signaler un problème de réseau ?",
    "Ah, bonne question.",
    "Attendez… je vérifie.",
    "Hmm, ce n'est pas ce que je vois de mon côté.",
    "D'accord, j'ai compris.",
    "Très bien.",
    "Excusez-moi, je vous ai coupé.",
    "Allez-y, je vous en prie.",
    "Non, ce n'est pas exact.",
    "Oui, tout à fait.",
    "C'est bien cela.",
    "Je préfère ne rien affirmer sans source.",
    "Vous avez dit Korhogo, c'est bien ça ?",
    "Répétez le nom, s'il vous plaît.",
    "Parfait, je note.",
    "Je reste avec vous.",
]

ENTETE = """SUTA — SCRIPT D'ENREGISTREMENT DE LA VOIX NATIVE (FRANÇAIS)
{barre}

Généré le {date} par outils/generer_script_voix.py — graine {graine}.
{total} phrases. Durée estimée : {minutes} minutes de parole utile,
soit deux à trois séances de deux heures avec les pauses et les reprises.

POURQUOI CE SCRIPT-LÀ
Les voix françaises disponibles sur étagère — métropolitaine, canadienne,
belge, suisse — déforment les toponymes ivoiriens. C'est la première chose
qu'on entend. Les blocs 2 et 3 sont donc bâtis sur les noms RÉELS du corpus
de SUTA, en couvrant les familles qui font trébucher : -kro, -kaha, -dougou,
-koro, et les noms à apostrophe initiale.

CONDITIONS D'ENREGISTREMENT
- Une seule personne, du début à la fin. Changer de voix en cours de route
  rend le corpus inutilisable.
- Pièce silencieuse, pas de studio nécessaire : fermer les fenêtres, éteindre
  ventilateur et climatiseur, téléphone en mode avion.
- Micro à vingt centimètres, distance CONSTANTE. La régularité compte plus
  que la qualité du micro.
- WAV, 22 050 Hz ou plus, mono, 16 bits. Aucun traitement : ni réverbération,
  ni réduction de bruit, ni compression. Le modèle apprendrait le traitement.
- Un fichier par phrase, nommé par son numéro : 0001.wav, 0002.wav…
- Ton naturel et régulier. Ni lecture de journal télévisé, ni sur-jeu.
- En cas d'erreur : marquer une pause de deux secondes et refaire la phrase
  entière. Ne jamais reprendre en milieu de phrase.
- Enregistrer trente secondes de silence de la pièce, en 0000.wav.

AVANT DE COMMENCER
La personne enregistrée devient la voix de SUTA. Un accord écrit est
nécessaire : usages autorisés, durée, conditions de retrait. Ce n'est pas une
formalité — sa voix sera clonée.

{barre}
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fiches", type=pathlib.Path, default=None, help="dossier supabase/fiches de SUTA-BOT")
    ap.add_argument("--sortie", type=pathlib.Path, default=pathlib.Path("voix/script-enregistrement-fr.txt"))
    ap.add_argument("--par-famille", type=int, default=22)
    a = ap.parse_args()

    alea = random.Random(GRAINE)
    toponymes = charger_toponymes(a.fiches)
    lieux = repartir(toponymes, a.par_famille, alea)

    phrases_lieux: list[str] = []
    for i, lieu in enumerate(lieux):
        gabarit = GABARITS_LIEU[i % len(GABARITS_LIEU)]
        autre = lieux[(i + 7) % len(lieux)]
        phrases_lieux.append(gabarit.format(lieu=lieu, autre=autre))

    blocs = [
        ("1. LA VOIX DE SUTA — ce qu'il dit tous les jours", AMORCE),
        ("2. TOPONYMES IVOIRIENS — le cœur du travail", phrases_lieux),
        ("3. VOCABULAIRE DE L'ANSUT", VOCABULAIRE),
        ("4. CHIFFRES, DATES ET UNITÉS", CHIFFRES),
        ("5. COUVERTURE PHONÉTIQUE DU FRANÇAIS", PHONETIQUE),
        ("6. PROSODIE — questions, accords, interruptions", PROSODIE),
    ]

    total = sum(len(p) for _, p in blocs)
    lignes: list[str] = []
    numero = 0
    for titre, phrases in blocs:
        lignes.append("")
        lignes.append(titre)
        lignes.append("-" * len(titre))
        for phrase in phrases:
            numero += 1
            lignes.append(f"{numero:04d}  {phrase}")

    from datetime import date

    entete = ENTETE.format(
        barre="=" * 66,
        date=date.today().isoformat(),
        graine=GRAINE,
        total=total,
        minutes=round(total * 4.5 / 60),
    )
    a.sortie.parent.mkdir(parents=True, exist_ok=True)
    a.sortie.write_text(entete + "\n".join(lignes) + "\n", encoding="utf-8")
    print(f"{a.sortie} — {total} phrases, {len(toponymes)} toponymes disponibles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
