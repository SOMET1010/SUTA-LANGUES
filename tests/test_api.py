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
    codes = {item["code"] for item in response.json()["langues"]}
    assert {"dyu_Latn", "bci_Latn", "any_Latn", "ati_Latn"} <= codes


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

