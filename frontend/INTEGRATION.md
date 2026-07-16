# Spectriq — frontend/backend integration notes

This frontend now talks to the real FastAPI backend instead of using mock
data. Here's what changed and how to run the whole thing.

## What was wired up

- **`lib/api.ts`** (new) — a typed client for every backend endpoint:
  upload, job status, list/get/update meeting, and chat (both
  non-streaming and SSE-streaming variants). All requests send an
  `X-User-Email` header, matching the backend's stub auth
  (`app/auth.py` — there's no real login system yet, just a
  get-or-create-by-email user).
- **`app/page.tsx`** (landing/login) — the form now actually does
  something: it validates the email, stores it in `localStorage`, and
  routes to `/dashboard`. The password field isn't sent anywhere,
  because the backend has no password check to send it to.
- **`app/dashboard/page.tsx`** — real file upload via `POST /upload`
  (with progress), a real "Recent Meetings" list via `GET /meetings`,
  loading/error states, and sign-out that clears the stored email.
- **`app/results/page.tsx`** — reads `?id=<meeting_id>` from the URL,
  polls `GET /meetings/{id}` every 2s until the pipeline finishes,
  renders the real summary/key decisions/open questions/transcript/action
  items, and the chat tab calls `POST /meetings/{id}/chat` for real
  grounded answers with expandable source citations. Download now
  exports the actual meeting content as a `.txt` file.

## Running it locally

**1. Backend** (needs Docker):

```bash
cd spectriq-backend/spectriq
cp .env.example .env
# fill in at least OPENAI_API_KEY (summarization) — VOYAGE_API_KEY and
# ANTHROPIC_API_KEY are only needed if you want the chat-with-meeting tab
# to work; everything else works without them.
docker compose up --build
```

This starts Postgres+pgvector, Redis, the API (`localhost:8000`), and the
Celery worker that actually does the transcription/summarization work.
Without the worker running, an upload will sit at "queued" forever.

**2. Frontend:**

```bash
cd spectriq-landing-page
cp .env.local.example .env.local   # NEXT_PUBLIC_API_URL=http://localhost:8000
npm install
npm run dev
```

Open `http://localhost:3000`, "sign in" with any email, upload a short
audio/video file, and you'll be dropped on `/results` polling live
pipeline progress.

## Known limitations to be aware of

- **Auth is still a stub.** Anyone can type any email and see whatever
  meetings exist for that email — there's no password verification
  anywhere. Fine for local development; replace `app/auth.py` (backend)
  and the login flow (frontend) with real auth before deploying this
  publicly.
- **No transcript speaker labels.** The backend's Whisper transcription
  doesn't do speaker diarization, so the transcript tab shows timestamped
  lines without speaker names (the earlier mock data had fake speaker
  names — that was never real).
- **Full pipeline needs one paid API key** (OpenAI, for summarization) —
  without it, uploads will fail at the summarization stage with a clear
  error message on the results page. The chat tab uses Gemini instead,
  which has a genuine free tier (no credit card required).

## Deploying to Render + Vercel

See `spectriq-backend/DEPLOY.md` for the full walkthrough (env vars,
storage backend, the `render.yaml` blueprint). Short version:

- Backend + worker + Postgres + Redis all go on Render — use the
  `render.yaml` blueprint in the backend folder to create all four in
  one shot (New -> Blueprint in the Render dashboard).
- Frontend goes on Vercel — set `NEXT_PUBLIC_API_URL` to your Render API
  URL.
- **Important:** once the API and worker are separate Render services,
  set `STORAGE_BACKEND=s3` (with a real bucket) on both — they don't
  share a disk, so the old "local" storage mode will get uploads stuck
  forever. `STORAGE_BACKEND=local` still works fine for the
  docker-compose setup on your own machine.
