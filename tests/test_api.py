import base64

from fastapi.testclient import TestClient

from suta_langues.main import create_app


class FakeBackend:
    model_card = "test-double"

    def transcribe(self, audio: bytes, mime: str, lang: str) -> str:
        assert audio == b"RIFF-test"
        assert mime == "audio/wav"
        assert lang == "dyu_Latn"
        return "i ni ce"


client = TestClient(create_app(FakeBackend()))


def test_lists_verified_ivorian_languages():
    response = client.get("/v1/langues")
    assert response.status_code == 200
    langues = response.json()["langues"]
    codes = {item["code"] for item in langues}
    # Les 24 langues vérifiées dans la liste officielle du modèle
    # (omnilingual-asr 0.2.0) — le dioula, véhiculaire du pays, en tête.
    assert len(langues) == 24
    assert langues[0]["code"] == "dyu_Latn"
    assert {"bam_Latn", "mos_Latn", "dyi_Latn", "wob_Latn", "ful_Latn", "hau_Latn"} <= codes


def test_suta_json_contract_transcribes_audio():
    response = client.post(
        "/v1/transcrire",
        json={
            "audio": base64.b64encode(b"RIFF-test").decode(),
            "mime": "audio/wav",
            "lang": "dyu_Latn",
        },
    )
    assert response.status_code == 200
    assert response.json()["texte"] == "i ni ce"
    assert response.json()["traduction"] is None


def test_rejects_language_not_enabled():
    response = client.post(
        "/v1/transcrire",
        json={"audio": "UklGRg==", "mime": "audio/wav", "lang": "eng_Latn"},
    )
    assert response.status_code == 422


def test_rejects_invalid_audio():
    response = client.post(
        "/v1/transcrire",
        json={"audio": "not-base64", "mime": "audio/wav", "lang": "dyu_Latn"},
    )
    assert response.status_code == 422



def test_requires_api_key_when_configured(monkeypatch):
    monkeypatch.setenv("LANGUES_API_KEY", "cle-de-test")
    payload = {
        "audio": base64.b64encode(b"RIFF-test").decode(),
        "mime": "audio/wav",
        "lang": "dyu_Latn",
    }
    sans_cle = client.post("/v1/transcrire", json=payload)
    assert sans_cle.status_code == 401
    mauvaise = client.post(
        "/v1/transcrire", json=payload, headers={"Authorization": "Bearer autre"}
    )
    assert mauvaise.status_code == 401
    bonne = client.post(
        "/v1/transcrire", json=payload, headers={"Authorization": "Bearer cle-de-test"}
    )
    assert bonne.status_code == 200
    assert bonne.json()["texte"] == "i ni ce"


def test_open_endpoints_stay_open_with_api_key(monkeypatch):
    monkeypatch.setenv("LANGUES_API_KEY", "cle-de-test")
    assert client.get("/health").status_code == 200
    assert client.get("/v1/langues").status_code == 200
