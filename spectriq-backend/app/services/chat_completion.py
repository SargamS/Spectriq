"""
"Chat with meeting" completion via the Gemini API.

Builds a grounded prompt from retrieved transcript chunks + conversation
history, then either streams the answer (for SSE responses) or returns it
in one shot.
"""
from collections.abc import Generator

from google import genai
from google.genai import types
from google.genai.errors import APIError

from app.config import settings
from app.models.transcript_chunk import TranscriptChunk

SYSTEM_PROMPT_TEMPLATE = """You are a helpful assistant. The user is currently viewing a meeting \
titled "{meeting_title}", and you have excerpts retrieved from that meeting's transcript below, \
each labeled with its timestamp range.

Rules:
- If the question is about the meeting, answer it using the transcript excerpts below, and \
reference the approximate timestamp(s) your answer is based on (e.g. "around 12:30").
- If the excerpts don't contain enough information to answer a meeting-related question, say so \
plainly rather than guessing.
- If the question is unrelated to the meeting (general knowledge, casual conversation, etc.), \
just answer it normally using your own knowledge.
- Keep answers concise and directly responsive to the question.

Transcript excerpts:
{context_block}"""


class ChatCompletionError(Exception):
    pass


def _format_timestamp(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _build_context_block(chunks: list[TranscriptChunk]) -> str:
    if not chunks:
        return "(no relevant excerpts were found for this question)"

    parts = []
    for chunk in chunks:
        ts_range = f"[{_format_timestamp(chunk.start_timestamp)}-{_format_timestamp(chunk.end_timestamp)}]"
        parts.append(f"{ts_range} {chunk.chunk_text}")
    return "\n\n".join(parts)


def _build_contents(conversation_history: list[dict], user_message: str) -> list[types.Content]:
    """
    Normalizes prior turns + the new user message into Gemini's Content
    format. Malformed history entries (missing/invalid role or content) are
    skipped rather than allowed to break the request. Gemini uses "model"
    instead of Claude/OpenAI's "assistant" for the other side of the turn.
    """
    contents = []
    for turn in conversation_history or []:
        role = turn.get("role")
        content = turn.get("content")
        if role not in ("user", "assistant") or not content:
            continue
        gemini_role = "model" if role == "assistant" else "user"
        contents.append(types.Content(role=gemini_role, parts=[types.Part(text=content)]))

    contents.append(types.Content(role="user", parts=[types.Part(text=user_message)]))
    return contents


def _client() -> genai.Client:
    if not settings.GEMINI_API_KEY:
        raise ChatCompletionError("GEMINI_API_KEY is not configured")
    return genai.Client(api_key=settings.GEMINI_API_KEY)


def generate_answer(
    meeting_title: str,
    chunks: list[TranscriptChunk],
    conversation_history: list[dict],
    user_message: str,
) -> str:
    """Non-streaming variant - returns the full answer text."""
    client = _client()
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        meeting_title=meeting_title or "Untitled meeting",
        context_block=_build_context_block(chunks),
    )
    contents = _build_contents(conversation_history, user_message)

    try:
        response = client.models.generate_content(
            model=settings.GEMINI_CHAT_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                max_output_tokens=1024,
            ),
        )
    except APIError as exc:
        raise ChatCompletionError(f"Gemini API request failed: {exc}") from exc

    return response.text or ""


def stream_answer(
    meeting_title: str,
    chunks: list[TranscriptChunk],
    conversation_history: list[dict],
    user_message: str,
) -> Generator[str, None, None]:
    """
    Streaming variant - yields text deltas as they arrive from Gemini.
    The caller (route) is responsible for wrapping these into SSE frames.
    """
    client = _client()
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        meeting_title=meeting_title or "Untitled meeting",
        context_block=_build_context_block(chunks),
    )
    contents = _build_contents(conversation_history, user_message)

    try:
        stream = client.models.generate_content_stream(
            model=settings.GEMINI_CHAT_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                max_output_tokens=1024,
            ),
        )
        for chunk in stream:
            if chunk.text:
                yield chunk.text
    except APIError as exc:
        raise ChatCompletionError(f"Gemini API streaming request failed: {exc}") from exc
