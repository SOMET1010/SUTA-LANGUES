from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Language:
    code: str
    name: str
    local_name: str
    family: str
    status: str = "a_valider"


# Sous-ensemble ivoirien vérifié dans la liste officielle supported_langs
# d'Omnilingual ASR. La présence du code ne préjuge pas de la qualité terrain.
IVORIAN_LANGUAGES = (
    Language("dyu_Latn", "Dioula", "Jula", "Mandé"),
    Language("bci_Latn", "Baoulé", "Baoulé", "Kwa"),
    Language("any_Latn", "Agni / Anyin", "Anyin", "Kwa"),
    Language("ati_Latn", "Attié", "Akyé", "Kwa"),
    Language("adj_Latn", "Adioukrou", "Adioukrou", "Kwa"),
    Language("abr_Latn", "Abron", "Abron", "Kwa"),
    Language("abi_Latn", "Abidji", "Abidji", "Kwa"),
    Language("dnj_Latn", "Dan", "Dan", "Mandé"),
    Language("gud_Latn", "Dida", "Yocoboué Dida", "Krou"),
    Language("nzi_Latn", "Nzema", "Nzema", "Kwa"),
)

LANGUAGE_BY_CODE = {item.code: item for item in IVORIAN_LANGUAGES}


def public_languages() -> list[dict[str, str]]:
    return [asdict(item) for item in IVORIAN_LANGUAGES]

