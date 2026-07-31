"""
Audio extraction/normalization via ffmpeg.

Encodes every upload (audio or video) down to 16kHz mono Opus-in-Ogg
rather than raw WAV. Whisper is happy with compressed input, and Opus at
a low bitrate is very size-efficient for speech - this matters because
Groq's hosted transcription endpoint (see app/services/transcription.py)
caps uploads at 25MB. Roughly:
    16kHz mono 16-bit PCM WAV  ~= 115MB/hour
    16kHz mono Opus @ 32kbps   ~=  14MB/hour
That alone keeps most meetings under the limit. For anything still over
it (very long recordings), split_audio_by_size() below splits the file
into time-boundary chunks that each fit, so transcription.py can send
them to Groq one at a time and stitch the results back together.
"""
import math
import os
import subprocess

FFMPEG_TIMEOUT_SECONDS = 60 * 30  # generous cap for long recordings
OPUS_BITRATE = "32k"


class AudioExtractionError(Exception):
    pass


def extract_audio(source_path: str, output_dir: str) -> str:
    """
    Runs ffmpeg to produce a 16kHz mono Opus/Ogg file from `source_path`.
    Works for both pure-audio and video inputs - ffmpeg will just pull
    the audio stream in either case.

    Returns the path to the generated .ogg file.
    """
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(source_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}.ogg")

    cmd = [
        "ffmpeg",
        "-y",              # overwrite output if it exists
        "-i", source_path,
        "-vn",              # drop video stream entirely
        "-ac", "1",         # mono
        "-ar", "16000",     # 16kHz sample rate (what Whisper expects)
        "-c:a", "libopus",
        "-b:a", OPUS_BITRATE,
        output_path,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=FFMPEG_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise AudioExtractionError(f"ffmpeg timed out after {FFMPEG_TIMEOUT_SECONDS}s") from exc

    if result.returncode != 0:
        raise AudioExtractionError(f"ffmpeg failed (exit {result.returncode}): {result.stderr[-2000:]}")

    if not os.path.exists(output_path):
        raise AudioExtractionError("ffmpeg reported success but no output file was produced")

    return output_path


def get_duration_seconds(path: str) -> float | None:
    """Uses ffprobe to read media duration; returns None if it can't be determined."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return float(result.stdout.strip())
    except (subprocess.TimeoutExpired, ValueError):
        return None


def split_audio_by_size(path: str, output_dir: str, max_bytes: int) -> list[str]:
    """
    Splits `path` into sequential chunks that each stay under `max_bytes`,
    for feeding to an API with an upload size cap (Groq's Whisper endpoint).

    Uses "-c copy" (no re-encoding) since the source is already 16kHz mono
    Opus - cutting on Opus frame boundaries is fast and lossless. Chunk
    duration is estimated from the file's overall bytes-per-second and
    given a 15% safety margin, since actual encoded size per second can
    vary slightly with how much speech vs. silence a chunk contains.

    Returns chunk paths in order. Caller is responsible for cleaning them
    up (they're written into `output_dir`, not touching the original file).
    """
    os.makedirs(output_dir, exist_ok=True)

    total_bytes = os.path.getsize(path)
    if total_bytes <= max_bytes:
        return [path]

    duration = get_duration_seconds(path)
    if not duration or duration <= 0:
        raise AudioExtractionError("Could not determine audio duration for chunking")

    bytes_per_second = total_bytes / duration
    safe_max_bytes = max_bytes * 0.85  # margin for per-chunk size variance
    chunk_seconds = max(30, int(safe_max_bytes / bytes_per_second))

    num_chunks = math.ceil(duration / chunk_seconds)
    base_name = os.path.splitext(os.path.basename(path))[0]
    ext = os.path.splitext(path)[1]

    chunk_paths = []
    for i in range(num_chunks):
        start = i * chunk_seconds
        chunk_path = os.path.join(output_dir, f"{base_name}_part{i:03d}{ext}")
        cmd = [
            "ffmpeg",
            "-y",
            "-ss", str(start),
            "-i", path,
            "-t", str(chunk_seconds),
            "-c", "copy",
            chunk_path,
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=FFMPEG_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            raise AudioExtractionError(f"ffmpeg timed out splitting chunk {i}") from exc

        if result.returncode != 0:
            raise AudioExtractionError(f"ffmpeg failed splitting chunk {i}: {result.stderr[-2000:]}")
        if not os.path.exists(chunk_path):
            raise AudioExtractionError(f"ffmpeg reported success but chunk {i} was not produced")

        chunk_paths.append(chunk_path)

    return chunk_paths
