"""
Summarization via the OpenAI API (Chat Completions).

Sends the transcript with a structured prompt requesting strict JSON
output (using OpenAI's JSON response-format mode), then parses/validates
that JSON. If parsing/validation fails, retries with an explicit
correction prompt before giving up.
"""
import json

import openai

from app.config import settings

MAX_JSON_RETRIES = 2

SYSTEM_PROMPT = """You are a precise meeting-notes assistant. You read raw meeting \
transcripts and produce structured, factual summaries. You never invent \
information that isn't supported by the transcript. If a field has no \
content, return an empty array/string for it rather than guessing."""

JSON_SCHEMA_DESCRIPTION = """Respond with ONLY a single valid JSON object with exactly \
these fields:

{
  "meeting_title": string,            // short, descriptive, auto-generated title
  "summary": string,                  // 3-6 sentence plain-language summary
  "key_decisions": [string, ...],     // decisions explicitly made during the meeting
  "action_items": [                   // concrete follow-up tasks
    {"text": string, "assignee": string | null}
  ],
  "open_questions": [string, ...]     // unresolved questions raised but not answered
}"""


class SummarizationError(Exception):
    pass


def _client() -> openai.OpenAI:
    if not settings.OPENAI_API_KEY:
        raise SummarizationError("OPENAI_API_KEY is not configured")
    return openai.OpenAI(api_key=settings.OPENAI_API_KEY)


REQUIRED_FIELDS = {"meeting_title", "summary", "key_decisions", "action_items", "open_questions"}


def _validate_shape(data: dict) -> None:
    missing = REQUIRED_FIELDS - data.keys()
    if missing:
        raise ValueError(f"Missing required fields in OpenAI response: {missing}")
    if not isinstance(data["key_decisions"], list):
        raise ValueError("key_decisions must be a list")
    if not isinstance(data["open_questions"], list):
        raise ValueError("open_questions must be a list")
    if not isinstance(data["action_items"], list):
        raise ValueError("action_items must be a list")
    for item in data["action_items"]:
        if not isinstance(item, dict) or "text" not in item:
            raise ValueError("Each action_item must be an object with a 'text' field")


def summarize(transcript_text: str) -> dict:
    """
    Calls OpenAI with the transcript and returns a validated dict:
        {meeting_title, summary, key_decisions, action_items, open_questions}

    Uses response_format={"type": "json_object"} so the model is
    constrained to return valid JSON; still validates the *shape* of
    that JSON and retries up to MAX_JSON_RETRIES times if fields are
    missing or malformed, telling the model exactly what went wrong.
    """
    client = _client()

    user_prompt = (
        f"{JSON_SCHEMA_DESCRIPTION}\n\n"
        f"Here is the meeting transcript:\n\n---\n{transcript_text}\n---"
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    last_error: Exception | None = None

    for attempt in range(1 + MAX_JSON_RETRIES):
        try:
            response = client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=messages,
                response_format={"type": "json_object"},
                max_tokens=2000,
            )
        except openai.OpenAIError as exc:
            raise SummarizationError(f"OpenAI API request failed: {exc}") from exc

        raw_text = response.choices[0].message.content or ""

        try:
            data = json.loads(raw_text)
            _validate_shape(data)
            return data
        except (json.JSONDecodeError, ValueError) as exc:
            last_error = exc
            # Feed the failure back to the model and ask it to correct itself.
            messages.append({"role": "assistant", "content": raw_text})
            messages.append({
                "role": "user",
                "content": (
                    f"That response did not match the required schema "
                    f"({exc}). Reply again with ONLY the corrected JSON object."
                ),
            })

    raise SummarizationError(
        f"OpenAI did not return valid JSON after {1 + MAX_JSON_RETRIES} attempts: {last_error}"
    )
