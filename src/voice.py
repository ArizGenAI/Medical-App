"""Voice symptom capture via recorded audio → OpenAI Whisper transcription."""

from __future__ import annotations

import io
from typing import Any

from src.config import get_openai_api_key
from src.logging_utils import get_logger

log = get_logger(__name__)


def transcribe_audio(file_bytes: bytes, filename: str = "symptom.wav") -> str:
    """
    Turn a recorded clip into text. Returns an empty string on failure
    (the UI shows the error; the app must not crash).
    """
    if not file_bytes:
        return ""
    key = get_openai_api_key()
    if not key:
        raise RuntimeError("OPENAI_API_KEY is required for voice transcription.")

    from openai import OpenAI

    client = OpenAI(api_key=key)
    buffer = io.BytesIO(file_bytes)
    buffer.name = filename
    try:
        result = client.audio.transcriptions.create(model="whisper-1", file=buffer)
    except Exception:
        log.exception("Whisper transcription failed")
        raise
    text = getattr(result, "text", None) or str(result)
    return (text or "").strip()


def audio_to_bytes(uploaded: Any) -> tuple[bytes, str]:
    """Accept Streamlit UploadedFile / audio values."""
    name = getattr(uploaded, "name", None) or "recording.wav"
    if hasattr(uploaded, "getvalue"):
        return uploaded.getvalue(), name
    if hasattr(uploaded, "read"):
        return uploaded.read(), name
    if isinstance(uploaded, bytes):
        return uploaded, name
    return b"", name
