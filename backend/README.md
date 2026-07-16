# Spectriq Backend

AI meeting summarizer API: upload audio/video -> extract audio (ffmpeg) ->
transcribe (faster-whisper) -> summarize (OpenAI API) -> structured
summary/decisions/action items.

## Local development

```bash
cp .env.example .env   # fill in OPENAI_API_KEY at minimum
docker compose up --build
```

This starts Postgres, Redis, the FastAPI app (`localhost:8000`), and a
Celery worker. Tables are auto-created on API startup.

Interactive API docs: `http://localhost:8000/docs`

## Auth note

There's no real auth system wired in - `app/auth.py` resolves the
"current user" from an `X-User-Id` (or `X-User-Email`) header, creating a
demo user if none is provided. Swap this for real JWT/OAuth/session auth
before shipping to production; every route already depends on
`get_current_user`, so that's the only file that needs to change.

## Pipeline

1. `POST /upload` saves the file, creates `Meeting` (status=`queued`) and
   `Job` (status=`queued`) rows, and enqueues
   `app.workers.tasks.process_meeting`.
2. The Celery task moves the job through
   `extracting -> transcribing -> summarizing -> done`, committing status
   after each stage so `GET /jobs/{job_id}/status` reflects live progress.
3. Any exception in a stage sets `status=failed` with `error_message` on
   both the `Job` and `Meeting` rows.

## Chat with meeting (RAG)

Once a meeting reaches `status=done`, `POST /meetings/{meeting_id}/chat`
answers questions grounded in that meeting's transcript:

```json
{
  "message": "What did we decide about the launch date?",
  "conversation_history": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}],
  "stream": false
}
```

- Set `"stream": true` to get a `text/event-stream` response (`delta`
  events as the answer is generated, then a `done` event with the full
  text + sources) instead of a single JSON body.
- Non-streaming responses look like
  `{"response": "...", "sources": [{"chunk_text": "...", "start_timestamp": 812.4}, ...]}`.
- Rate limited to `CHAT_RATE_LIMIT_PER_HOUR` (default 20) messages per
  meeting per hour via a Redis counter; exceeding it returns `429` with a
  `Retry-After` header.
- If the meeting hasn't finished the `indexing` pipeline stage yet, the
  endpoint returns `409` with a clear "still being processed" message
  rather than an empty/wrong answer.

Under the hood: transcript segments are grouped into ~300-word,
50-word-overlap chunks on Whisper's own segment boundaries
(`app/services/chunking.py`), embedded via the Gemini API
(`app/services/embeddings.py`), and stored in a pgvector column
(`TranscriptChunk.embedding`). Chat queries are embedded the same way and
matched via cosine similarity (`app/services/retrieval.py`) before being
fed to Gemini as grounding context (`app/services/chat_completion.py`).

## Production notes

- Swap `Base.metadata.create_all` for Alembic migrations once the schema
  needs to evolve without data loss.
- Swap `app/storage.py`'s local-disk implementation for S3/GCS.
- Run `api` and `worker` as separate services/processes (see
  docker-compose.yml `command` overrides) pointed at managed
  Postgres/Redis.
- `WHISPER_DEVICE=cuda` if the worker has a GPU available - much faster
  than CPU for longer meetings.
