"""
Splits a transcript into overlapping chunks for embedding/retrieval.

We chunk on Whisper's own segment boundaries rather than re-splitting raw
text: faster-whisper's VAD-based segments already correspond closely to
natural sentence/phrase boundaries and carry per-segment timestamps, so
grouping *whole* segments into chunks gives us sentence-boundary-respecting
chunks with accurate start/end timestamps "for free".
"""
from dataclasses import dataclass

from app.config import settings


@dataclass
class TranscriptChunkData:
    chunk_text: str
    start_timestamp: float
    end_timestamp: float
    speaker_label: str | None = None  # not populated until diarization exists upstream


def _word_count(text: str) -> int:
    return len(text.split())


def chunk_transcript(
    segments: list[dict],
    target_words: int = None,
    overlap_words: int = None,
) -> list[TranscriptChunkData]:
    """
    Groups Whisper segments into ~target_words-sized chunks with
    ~overlap_words of trailing context carried into the next chunk.

    `segments` is the same list stored on Meeting.transcript_segments:
    [{"start": float, "end": float, "text": str}, ...]
    """
    target_words = target_words or settings.CHUNK_TARGET_WORDS
    overlap_words = overlap_words or settings.CHUNK_OVERLAP_WORDS

    if not segments:
        return []

    chunks: list[TranscriptChunkData] = []
    current: list[dict] = []
    current_word_count = 0

    def flush_chunk(next_leading_overlap: bool = True) -> list[dict]:
        """Finalizes `current` into a chunk and returns the segments that
        should carry over as overlap into the next chunk."""
        nonlocal current, current_word_count

        if not current:
            return []

        text = " ".join(seg["text"].strip() for seg in current if seg["text"].strip())
        chunks.append(
            TranscriptChunkData(
                chunk_text=text,
                start_timestamp=current[0]["start"],
                end_timestamp=current[-1]["end"],
            )
        )

        if not next_leading_overlap:
            return []

        # Walk backwards from the end of `current`, collecting segments
        # until we've gathered ~overlap_words worth of trailing context.
        overlap_segments: list[dict] = []
        overlap_count = 0
        for seg in reversed(current):
            seg_words = _word_count(seg["text"])
            if overlap_count >= overlap_words:
                break
            overlap_segments.insert(0, seg)
            overlap_count += seg_words

        return overlap_segments

    for segment in segments:
        seg_words = _word_count(segment.get("text", ""))
        if seg_words == 0:
            continue

        current.append(segment)
        current_word_count += seg_words

        if current_word_count >= target_words:
            carry_over = flush_chunk()
            current = carry_over
            current_word_count = sum(_word_count(s["text"]) for s in current)

    # Flush whatever's left as the final chunk (no overlap needed after it).
    if current:
        flush_chunk(next_leading_overlap=False)

    return chunks
