from __future__ import annotations

import base64
import binascii
import hmac
import os
from pathlib import Path
from time import perf_counter

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

from .backend import ASRBackend, BackendUnavailable, OmnilingualBackend
from .languages import LANGUAGE_BY_CODE, public_languages

MAX_AUDIO_BYTES = int(os.getenv("MAX_AUDIO_BYTES", str(12 * 1024 * 1024)))
ALLOWED_MIMES = {"audio/wav", "audio/x-wav", "audio/flac", "audio/mpeg", "audio/mp4", "audio/webm", "audio/ogg"}


class TranscriptionRequest(BaseModel):
    audio: str = Field(description="Audio encodé en base64, avec ou sans préfixe data:audio/...;base64,")
    mime: str
    lang: str

    @field_validator("mime")
    @classmethod
    def validate_mime(cls, value: str) -> str:
        value = value.lower().strip()
        if value not in ALLOWED_MIMES:
            raise ValueError("Format audio non accepté")
        return value

    @field_validator("lang")
    @classmethod
    def validate_lang(cls, value: str) -> str:
        if value not in LANGUAGE_BY_CODE:
            raise ValueError("Langue ivoirienne non activée")
        return value


class TranscriptionResponse(BaseModel):
    texte: str
    traduction: str | None = None
    lang: str
    modele: str
    duree_ms: int


def require_api_key(authorization: str | None) -> None:
    """Clé d'accès du service (LANGUES_API_KEY) — SUTA l'envoie en Bearer
    (LABO_ASR_KEY de son côté). Lue à chaque appel pour rester testable.
    Vide = service ouvert (développement local uniquement) ; en production
    la clé est OBLIGATOIRE, en plus de la passerelle réseau (README)."""
    expected = os.getenv("LANGUES_API_KEY", "").strip()
    if not expected:
        return
    provided = (authorization or "").removeprefix("Bearer ").strip()
    if not hmac.compare_digest(provided.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Clé d'accès absente ou invalide")


def decode_audio(value: str) -> bytes:
    payload = value.split(",", 1)[1] if value.startswith("data:") and "," in value else value
    try:
        audio = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Audio base64 invalide") from exc
    if not audio:
        raise HTTPException(status_code=422, detail="Audio vide")
    if len(audio) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio trop volumineux")
    return audio


def create_app(backend: ASRBackend | None = None) -> FastAPI:
    engine = backend or OmnilingualBackend()
    app = FastAPI(title="SUTA-LANGUES", version="0.1.0")

    @app.get("/")
    def tester():
        return FileResponse(Path(__file__).parent / "static" / "index.html")

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "suta-langues"}

    @app.get("/v1/langues")
    def langues():
        return {"langues": public_languages(), "avertissement": "Présence modèle confirmée; qualité terrain à valider."}

    @app.post("/v1/transcrire", response_model=TranscriptionResponse)
    def transcrire(request: TranscriptionRequest, authorization: str | None = Header(default=None)):
        require_api_key(authorization)
        audio = decode_audio(request.audio)
        started = perf_counter()
        try:
            texte = engine.transcribe(audio, request.mime, request.lang)
        except BackendUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Échec de la transcription") from exc
        model = getattr(engine, "model_card", engine.__class__.__name__)
        return TranscriptionResponse(
            texte=texte,
            lang=request.lang,
            modele=str(model),
            duree_ms=round((perf_counter() - started) * 1000),
        )

    return app


app = create_app()

