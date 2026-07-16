"""
Transcription via Groq's hosted Whisper API.

This replaces running faster-whisper locally. Groq runs Whisper on their
own inference hardware (fast, and free-tier), which sidesteps the problem
of Render's free-tier web service having far too little CPU to transcribe
anything but a very short clip in a reasonable time.

Groq's audio endpoint caps uploads at 25MB. Audio is already compressed
to a low-bitrate Opus/Ogg at extraction time (see audio_extraction.py) to
keep most meetings under that on their own; for anything still over the
limit, this module splits the file into sequential chunks and stitches
the per-chunk transcripts back into one result with continuous timestamps.
"""
import os
import shutil
import tempfile

import groq

from app.config import settings
from app.services import audio_extraction

GROQ_MAX_AUDIO_BYTES = 25 * 1024 * 1024


class TranscriptionError(Exception):
    pass


def _client() -> groq.Groq:
    if not settings.GROQ_API_KEY:
        raise TranscriptionError("GROQ_API_KEY is not configured")
    return groq.Groq(api_key=settings.GROQ_API_KEY)


def _segment_field(segment, key: str):
    """Groq's SDK returns segments as dict-like or attribute-like objects
    depending on version - handle both rather than assuming one shape."""
    if isinstance(segment, dict):
        return segment[key]
    return getattr(segment, key)


def _transcribe_file(client: groq.Groq, path: str) -> dict:
    """Sends a single file (already under Groq's size cap) for transcription."""
    try:
        with open(path, "rb") as f:
            result = client.audio.transcriptions.create(
                file=(os.path.basename(path), f.read()),
                model=settings.GROQ_WHISPER_MODEL,
                response_format="verbose_json",
                timestamp_granularities=["segment"],
            )
    except groq.GroqError as exc:
        raise TranscriptionError(f"Groq transcription request failed: {exc}") from exc
    except OSError as exc:
        raise TranscriptionError(f"Could not read audio file: {exc}") from exc

    raw_segments = getattr(result, "segments", None) or []

    segments = []
    text_parts = []
    for seg in raw_segments:
        clean_text = str(_segment_field(seg, "text")).strip()
        segments.append({
            "start": _segment_field(seg, "start"),
            "end": _segment_field(seg, "end"),
            "text": clean_text,
        })
        text_parts.append(clean_text)

    return {
        "segments": segments,
        "full_text": (getattr(result, "text", None) or " ".join(text_parts)).strip(),
        "language": getattr(result, "language", None) or "unknown",
    }


def transcribe(wav_path: str) -> dict:
    """
    Transcribes the given audio file via Groq, transparently splitting it
    into chunks first if it's over Groq's 25MB upload cap.

    Returns:
        {
            "segments": [{"start": float, "end": float, "text": str}, ...],
            "full_text": str,
            "language": str,
        }
    """
    client = _client()
    file_size = os.path.getsize(wav_path)

    if file_size <= GROQ_MAX_AUDIO_BYTES:
        result = _transcribe_file(client, wav_path)
        if not result["segments"]:
            raise TranscriptionError("Groq produced no segments (silent or unreadable audio?)")
        return result

    # Oversized: split into chunks, transcribe each, and stitch the
    # results back together with continuous timestamps.
    tmp_dir = tempfile.mkdtemp(prefix="transcribe_chunks_")
    try:
        chunk_paths = audio_extraction.split_audio_by_size(wav_path, tmp_dir, GROQ_MAX_AUDIO_BYTES)

        all_segments = []
        text_parts = []
        language = "unknown"
        time_offset = 0.0

        for chunk_path in chunk_paths:
            chunk_result = _transcribe_file(client, chunk_path)

            for seg in chunk_result["segments"]:
                all_segments.append({
                    "start": seg["start"] + time_offset,
                    "end": seg["end"] + time_offset,
                    "text": seg["text"],
                })
            if chunk_result["full_text"]:
                text_parts.append(chunk_result["full_text"])
            if language == "unknown":
                language = chunk_result["language"]

            chunk_duration = audio_extraction.get_duration_seconds(chunk_path) or 0.0
            time_offset += chunk_duration

        if not all_segments:
            raise TranscriptionError("Groq produced no segments (silent or unreadable audio?)")

        return {
            "segments": all_segments,
            "full_text": " ".join(text_parts),
            "language": language,
        }
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
