from __future__ import annotations

import os
import tempfile
from pathlib import Path
from threading import Lock
from typing import Protocol


class ASRBackend(Protocol):
    def transcribe(self, audio: bytes, mime: str, lang: str) -> str: ...


class BackendUnavailable(RuntimeError):
    pass


class OmnilingualBackend:
    """Chargement paresseux : le modèle n'est téléchargé qu'au premier appel."""

    def __init__(self, model_card: str | None = None) -> None:
        self.model_card = model_card or os.getenv("OMNIASR_MODEL", "omniASR_CTC_300M_v2")
        self._pipeline = None
        self._lock = Lock()

    def _get_pipeline(self):
        if self._pipeline is not None:
            return self._pipeline
        with self._lock:
            if self._pipeline is None:
                try:
                    from omnilingual_asr.models.inference.pipeline import ASRInferencePipeline
                except ImportError as exc:
                    raise BackendUnavailable(
                        "Le moteur Omnilingual ASR n'est pas installé. Installez l'option 'asr'."
                    ) from exc
                self._pipeline = ASRInferencePipeline(model_card=self.model_card)
        return self._pipeline

    def transcribe(self, audio: bytes, mime: str, lang: str) -> str:
        suffix = {
            "audio/wav": ".wav",
            "audio/x-wav": ".wav",
            "audio/flac": ".flac",
            "audio/mpeg": ".mp3",
            "audio/mp4": ".m4a",
            "audio/webm": ".webm",
            "audio/ogg": ".ogg",
        }.get(mime, ".audio")
        path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
                handle.write(audio)
                path = handle.name
            result = self._get_pipeline().transcribe([path], lang=[lang], batch_size=1)
            if not result or not str(result[0]).strip():
                raise RuntimeError("Le moteur ASR a renvoyé une transcription vide.")
            return str(result[0]).strip()
        finally:
            if path:
                Path(path).unlink(missing_ok=True)

