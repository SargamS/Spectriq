"""
Transcription via faster-whisper.

The model is loaded lazily and cached at module scope so the process
only pays the model-load cost once, not per job.
"""
from functools import lru_cache

from app.config import settings


class TranscriptionError(Exception):
    pass


@lru_cache(maxsize=1)
def _get_model():
    # Imported lazily so that services which don't need Whisper (e.g. tests
    # that only exercise routing) don't pay the import cost.
    from faster_whisper import WhisperModel

    return WhisperModel(
        settings.WHISPER_MODEL_SIZE,
        device=settings.WHISPER_DEVICE,
        compute_type=settings.WHISPER_COMPUTE_TYPE,
    )


def transcribe(wav_path: str) -> dict:
    """
    Runs Whisper over the given WAV file.

    Returns:
        {
            "segments": [{"start": float, "end": float, "text": str}, ...],
            "full_text": str,
            "language": str,
        }
    """
    model = _get_model()

    try:
        segments_iter, info = model.transcribe(wav_path, beam_size=5, vad_filter=True)
    except Exception as exc:  # faster-whisper doesn't expose a narrow exception type
        raise TranscriptionError(f"Whisper transcription failed: {exc}") from exc

    segments = []
    text_parts = []
    for seg in segments_iter:
        clean_text = seg.text.strip()
        segments.append({"start": seg.start, "end": seg.end, "text": clean_text})
        text_parts.append(clean_text)

    if not segments:
        raise TranscriptionError("Whisper produced no segments (silent or unreadable audio?)")

    return {
        "segments": segments,
        "full_text": " ".join(text_parts),
        "language": info.language,
    }
