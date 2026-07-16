<div align="center">

# 🎙️ Spectriq

**Upload a meeting recording. Get a transcript, an AI summary, action items, and a chat interface to ask questions about it — automatically.**

[![Backend](https://img.shields.io/badge/backend-FastAPI-009688)](./spectriq-backend)
[![Frontend](https://img.shields.io/badge/frontend-Next.js%2016-000000)](./spectriq-landing-page)
[![Deploy](https://img.shields.io/badge/deploy-Render%20%2B%20Vercel-9146FF)](#-deployment)
[![Cost](https://img.shields.io/badge/infra%20cost-%240%2Fmo-2ea44f)](#-cost-breakdown)

### 🔗 [Live Demo](https://spectriq.vercel.app/) · [Report Bug](https://github.com/SargamS/SamudraSetu-/issues) · [Request Feature](https://github.com/SargamS/SamudraSetu-/issues)

</div>

## What it does

Drop in an audio or video file of a meeting, and Spectriq:

1. **Extracts** the audio track (ffmpeg)
2. **Transcribes** it with speaker-timestamped segments (Groq-hosted Whisper)
3. **Summarizes** it into a title, plain-language summary, key decisions, action items, and open questions (Groq / Llama 3.3)
4. **Indexes** the transcript so you can **chat with the meeting** afterward — ask "what did we decide about the launch date?" and get an answer grounded in the actual transcript, with timestamps (Jina embeddings + Gemini)

All of it runs on infrastructure that costs **$0/month** — see [Cost breakdown](#-cost-breakdown).

---

## Architecture

```
┌─────────────────────┐       ┌──────────────────────────────────────────┐
│   Next.js Frontend  │──────▶│              FastAPI Backend             │
│  (Vercel)           │       │              (Render, free tier)         │
│                     │       │                                          │
│  Upload → Dashboard │       │  POST /upload ──▶ background thread:     │
│  → Meeting detail   │       │    1. extract audio    (ffmpeg)          │
│  → Chat             │       │    2. transcribe        (Groq Whisper)   │
└──────────┬──────────┘       │    3. summarize          (Groq / Llama)  │
           │                  │    4. chunk + embed        (Jina)        │
           │  polls           │    5. done                               │
           ▼                  │                                          │
   GET /meetings/{id}         │  POST /meetings/{id}/chat ──▶ retrieval  │
                              │    (pgvector cosine search) + Gemini     │
                              └─────────────────┬────────────────────────┘
                                                │
                                                ▼
                                     ┌─────────────────────┐
                                     │ Postgres + pgvector │
                                     │  (Neon, free tier)  │
                                     └─────────────────────┘
```

The entire processing pipeline runs **in-process on a background thread** inside the API service (see [`app/background.py`](./spectriq-backend/app/background.py)) rather than a separate worker + queue. That's a deliberate trade-off: it means the whole backend fits on a single free Render web service instead of requiring a paid Background Worker + Redis instance.

---

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Frontend | Next.js 16, React 19, Tailwind | App Router, fast iteration |
| Backend | FastAPI + SQLAlchemy | Async-friendly, typed, great docs generation |
| Database | Postgres + pgvector (Neon) | Permanent free tier, no card, vector search built in |
| Transcription | Groq (hosted Whisper `whisper-large-v3-turbo`) | Fast, free tier, doesn't need local GPU/CPU |
| Summarization | Groq (`llama-3.3-70b-versatile`) | OpenAI-compatible API, generous free tier |
| Embeddings | Jina AI (`jina-embeddings-v3`) | Free tier, strong retrieval quality |
| Chat answers | Gemini (`gemini-flash-latest`) | Free tier, long context |
| Audio processing | ffmpeg → 16kHz mono Opus/Ogg | Small file size, fits under API upload limits |
| Hosting | Render (API) + Vercel (frontend) + Neon (DB) | All genuinely free, no expiry, no card |

## Project structure

```
Spectriq-main/
├── spectriq-backend/          # FastAPI API + processing pipeline
│   ├── app/
│   │   ├── routes/            # upload, meetings, jobs, chat
│   │   ├── services/          # audio_extraction, transcription, summarization,
│   │   │                      #   embeddings, chunking, retrieval, chat_completion
│   │   ├── workers/tasks.py   # the pipeline itself (extract → transcribe → summarize → index)
│   │   ├── models/            # Meeting, Job, TranscriptChunk, User
│   │   └── background.py      # in-process background thread runner
│   ├── render.yaml            # one-click Render Blueprint deploy
│   └── DEPLOY.md              # step-by-step deployment guide
└── spectriq-landing-page/     # Next.js frontend
    └── app/
        ├── page.tsx           # landing/sign-in
        ├── dashboard/         # meeting list + upload
        └── results/           # meeting detail: summary / transcript / action items / chat
```

---

## Getting started locally

### Backend

```bash
cd spectriq-backend
cp .env.example .env     # fill in GROQ_API_KEY at minimum
docker compose up --build
```

This starts Postgres (with pgvector) and the API at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`. Tables are created automatically on startup.

### Frontend

```bash
cd spectriq-landing-page
npm install
npm run dev
```

Runs at `http://localhost:3000`. Point it at your local backend via the API base URL in `lib/api.ts` (see [`INTEGRATION.md`](./spectriq-landing-page/INTEGRATION.md)).

---

## Required environment variables

| Variable | Required for | Get it at |
|---|---|---|
| `DATABASE_URL` | everything | your Postgres/Neon connection string |
| `GROQ_API_KEY` | transcription + summarization | [console.groq.com](https://console.groq.com) |
| `JINA_API_KEY` | chat-with-meeting embeddings | [jina.ai](https://jina.ai) |
| `GEMINI_API_KEY` | chat-with-meeting answers | [aistudio.google.com](https://aistudio.google.com) |

Full list with defaults lives in [`app/config.py`](./spectriq-backend/app/config.py).

---

## Deployment

The backend deploys as a single free Render web service; the database lives on Neon (permanent free tier, unlike Render's own Postgres which auto-deletes after 30 days); the frontend deploys to Vercel.

**Full walkthrough:** [`spectriq-backend/DEPLOY.md`](./spectriq-backend/DEPLOY.md)

Quick version:
1. Create a free Neon Postgres project, run `CREATE EXTENSION IF NOT EXISTS vector;`
2. Get `GROQ_API_KEY`, `JINA_API_KEY`, `GEMINI_API_KEY`
3. Render → New → Blueprint → point at `spectriq-backend/render.yaml` → fill in env vars
4. Deploy the frontend to Vercel, set `ALLOWED_ORIGINS` on the backend to your Vercel URL

---

## The pipeline, stage by stage

`POST /upload` creates a `Meeting` + `Job` (both `status=queued`) and kicks off processing on a background thread. Each stage updates status so the frontend can show live progress via `GET /meetings/{id}`:

| Stage | What happens | Powered by |
|---|---|---|
| `extracting` | Pull/convert audio to 16kHz mono Opus | ffmpeg |
| `transcribing` | Speech → timestamped text segments | Groq (Whisper) |
| `summarizing` | Transcript → title, summary, decisions, action items, open questions (strict JSON) | Groq (Llama 3.3) |
| `indexing` | Chunk transcript + embed for retrieval | Jina |
| `done` | Ready — chat unlocks | — |

If any stage throws, the job/meeting move to `status=failed` with a human-readable `error_message` instead of hanging silently. A failed meeting can be **retried** via `POST /meetings/{id}/retry`, which resumes from the failed stage rather than redoing already-completed (expensive) work.

**Long recordings:** audio over Groq's 25MB upload cap is automatically split into sequential chunks, transcribed individually, and stitched back into one continuous transcript with correct timestamps — no manual splitting needed.

## Chat with your meeting

Once a meeting hits `done`, ask it questions:

```json
POST /meetings/{id}/chat
{
  "message": "What did we decide about the launch date?",
  "conversation_history": [],
  "stream": false
}
```

Under the hood: the transcript is chunked on natural segment boundaries (~300 words, 50-word overlap), embedded via Jina, and stored in a `pgvector` column. Your question gets embedded the same way, matched via cosine similarity, and the top matches are fed to Gemini as grounding context — so answers are traceable back to specific moments in the transcript, not hallucinated.

---

## Roadmap ideas

- [ ] Real authentication (currently identifies users by header, see `app/auth.py`)
- [ ] Speaker diarization (who said what)
- [ ] Frontend "Retry" button wired to `POST /meetings/{id}/retry`
- [ ] Export summary as PDF/Notion/Slack
- [ ] Alembic migrations instead of `create_all` for safer schema evolution

---

<div align="center">
Built with FastAPI, Next.js, Groq, Jina, and Gemini — running entirely on free infrastructure.
</div>
