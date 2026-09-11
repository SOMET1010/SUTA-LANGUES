from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Language:
    code: str
    name: str
    local_name: str
    family: str
    status: str = "a_valider"


# Langues de Côte d'Ivoire présentes dans la liste officielle
# `supported_langs` d'Omnilingual ASR (lang_ids.py du paquet
# omnilingual-asr 0.2.0, revérifiée le 11/09/2026 — 1 668 langues au
# total). La présence du code ne préjuge PAS de la qualité terrain :
# chaque langue reste `a_valider` tant que des locuteurs n'ont pas jugé
# les transcriptions (labo langues de SUTA). Le dioula ouvre la liste :
# véhiculaire du pays, c'est la première oreille du pilote.
#
# Familles alignées sur le labo SUTA : Mandé, Kwa, Krou, Gur, Véhiculaire.
IVORIAN_LANGUAGES = (
    Language("dyu_Latn", "Dioula", "Julakan", "Mandé"),
    Language("bam_Latn", "Bambara", "Bamanankan", "Mandé"),
    Language("dnj_Latn", "Dan (Yacouba)", "Dan", "Mandé"),
    Language("neb_Latn", "Toura", "Toura", "Mandé"),
    Language("mev_Latn", "Mano", "Maa", "Mandé"),
    Language("bci_Latn", "Baoulé", "Baoulé", "Kwa"),
    Language("any_Latn", "Agni / Anyin", "Anyin", "Kwa"),
    Language("ati_Latn", "Attié", "Akyé", "Kwa"),
    Language("abi_Latn", "Abidji", "Abidji", "Kwa"),
    Language("adj_Latn", "Adioukrou", "Adioukrou", "Kwa"),
    Language("abr_Latn", "Abron", "Abron", "Kwa"),
    Language("nzi_Latn", "Nzema", "Nzema", "Kwa"),
    Language("wob_Latn", "Wobé", "Wè", "Krou"),
    Language("nwb_Latn", "Nyabwa", "Nyabwa", "Krou"),
    Language("ktj_Latn", "Krumen plapo", "Krumen", "Krou"),
    Language("ted_Latn", "Krumen tépo", "Krumen", "Krou"),
    Language("gud_Latn", "Dida", "Yocoboué Dida", "Krou"),
    Language("dyi_Latn", "Sénoufo djimini", "Djimini", "Gur"),
    Language("spp_Latn", "Sénoufo supyiré", "Supyiré", "Gur"),
    Language("myk_Latn", "Sénoufo mamara", "Mamara", "Gur"),
    Language("lob_Latn", "Lobi", "Lobiri", "Gur"),
    Language("mos_Latn", "Mooré", "Mooré", "Véhiculaire"),
    Language("ful_Latn", "Peul", "Fulfulde", "Véhiculaire"),
    Language("hau_Latn", "Haoussa", "Hausa", "Véhiculaire"),
)

LANGUAGE_BY_CODE = {item.code: item for item in IVORIAN_LANGUAGES}


def public_languages() -> list[dict[str, str]]:
    return [asdict(item) for item in IVORIAN_LANGUAGES]
