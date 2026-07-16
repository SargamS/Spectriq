"""
Audio extraction/normalization via ffmpeg.

Whisper wants 16kHz mono PCM WAV. We run every upload (audio or video)
through ffmpeg so transcription always gets a consistent input format,
and so video files get their audio track pulled out.
"""
import os
import subprocess

FFMPEG_TIMEOUT_SECONDS = 60 * 30  # generous cap for long recordings


class AudioExtractionError(Exception):
    pass


def extract_audio(source_path: str, output_dir: str) -> str:
    """
    Runs ffmpeg to produce a 16kHz mono WAV from `source_path`.
    Works for both pure-audio and video inputs - ffmpeg will just pull
    the audio stream in either case.

    Returns the path to the generated WAV file.
    """
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(source_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}.wav")

    cmd = [
        "ffmpeg",
        "-y",              # overwrite output if it exists
        "-i", source_path,
        "-vn",              # drop video stream entirely
        "-ac", "1",         # mono
        "-ar", "16000",     # 16kHz sample rate (what Whisper expects)
        "-f", "wav",
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
