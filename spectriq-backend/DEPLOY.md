# Deploying the Spectriq backend to Render (free tier, no expiry)

## What gets created

Using the included `render.yaml` blueprint, Render creates 1 thing:

- **spectriq-api** — Web Service — the FastAPI app (free plan). It also
  runs the meeting-processing pipeline (audio extraction ->
  transcription -> summarization -> indexing) in-process on a background
  thread instead of a separate worker.

The database lives outside Render, on **Neon** (neon.com) instead -
Render's own free Postgres auto-deletes after 30 days, while Neon's free
tier is permanent with no credit card and no expiry, and has pgvector
built in (needed for the "chat with meeting" embeddings).

This setup used to also include a Redis instance and a separate
Background Worker service for a Celery-based pipeline. That's gone:
Background Workers have no free tier on Render at all, so the old setup
could never actually be deployed for $0. Running the pipeline in-process
(see `app/background.py`) means the whole thing fits on one free Render
web service + one free Neon database, no card required anywhere.

## Step 1 — Create your free Neon database

1. Go to **console.neon.tech** and sign up (no credit card required).
2. Create a new project. Pick any name/region.
3. On the project's dashboard, find the **Connection string** (usually
   shown right on the overview page, or under "Connect"). It looks like:
   ```
   postgresql://<user>:<password>@<host>/<dbname>?sslmode=require
   ```
4. Turn that into what this app needs by changing `postgresql://` to
   `postgresql+psycopg2://` (SQLAlchemy needs the `+psycopg2` part to
   pick the right driver) - keep the rest, including `?sslmode=require`,
   exactly as Neon gave it to you. End result looks like:
   ```
   postgresql+psycopg2://<user>:<password>@<host>/<dbname>?sslmode=require
   ```
5. In Neon's **SQL Editor** (in the dashboard), run once:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
   (the app also tries this itself on startup, so this is just a safety
   net in case of a timing race on the very first deploy.)
6. Keep that connection string handy - it's your `DATABASE_URL`.

## Step 2 — Get your other API keys

- **OpenAI** (required) — platform.openai.com — used for the actual
  meeting summary. No free tier; pay-as-you-go.
- **Gemini / Google AI** (optional) — aistudio.google.com — only needed
  for the "chat with meeting" tab (used for both embeddings and chat
  answers). Has a genuine free tier, no credit card required.

## Step 3 — Deploy via Blueprint

1. Push this folder to a GitHub repo.
2. In the Render dashboard: **New -> Blueprint**, pick that repo.
   - **Branch**: whichever branch has your code (usually `main`)
   - **Blueprint Path**: point it at wherever `render.yaml` actually
     lives in your repo (e.g. `backend/render.yaml` if your backend
     code is inside a `backend` folder rather than the repo root)
3. Render reads `render.yaml` and shows you a preview of the 1 service
   above. Click **Apply**. Wait for the build to finish (the first
   build is slow - it's installing ffmpeg, faster-whisper, and
   downloading the Whisper model weights).
4. Once created, go into **spectriq-api**'s "Environment" tab and fill
   in every value marked `sync: false` in `render.yaml`:
   - `DATABASE_URL` — your Neon connection string from Step 1
   - `OPENAI_API_KEY`
   - `GEMINI_API_KEY` (optional)

## Step 4 — Verify it's alive

Visit `https://<your-api-service>.onrender.com/health` — you should see
`{"status": "ok"}`.

## Step 5 — Connect the frontend

Once your Vercel deployment is live (see the frontend's own README),
come back and update `ALLOWED_ORIGINS` on **spectriq-api** to your real
Vercel URL(s), comma-separated, e.g.:

```
ALLOWED_ORIGINS=https://spectriq.vercel.app,https://spectriq-yourname.vercel.app
```

Without this, the browser will block every request from your frontend
with a CORS error even though the backend itself is working fine.

## Free-tier caveats worth knowing

- **Free web services on Render spin down when idle.** After a period
  with no incoming HTTP traffic, Render spins the instance down; the
  next request takes ~30-60s to wake it back up. The frontend polling
  `GET /meetings/{id}` every couple seconds while a job is processing
  keeps the instance awake during that window - it may just go back to
  sleep between visits, which is normal.
- **Neon's compute also scales to zero when idle** - a separate,
  smaller-scale version of the same idea. It wakes up in a few hundred
  milliseconds on the next query, so this isn't something you need to
  work around; it just means the very first query after a quiet period
  is slightly slower than usual.
- **Uploaded files are not persisted long-term.** With `STORAGE_BACKEND=local`,
  files live on the Render instance's own disk only for the life of that
  instance/deploy. That's fine for processing (transcript/summary end
  up in Neon's Postgres, which is what the frontend actually reads
  back), but don't rely on re-downloading the original audio/video after
  a redeploy or restart.
- **Neon's free tier has monthly compute-hour limits** (currently around
  100 compute-hours/project/month) and 0.5 GB storage per project - both
  generous for a personal project, but worth knowing if you scale up.

## Troubleshooting

- **App won't start / DB connection errors** → double-check
  `DATABASE_URL` has `+psycopg2` after `postgresql` and `?sslmode=require`
  at the end - Neon requires SSL and SQLAlchemy needs the driver name.
- **Uploads stuck on "queued" forever** → check the API's logs on
  Render for an error early in the pipeline (e.g. a crash right at
  startup would prevent the background thread from ever running).
- **Uploads fail at "extracting audio"** → almost always a missing/invalid
  `OPENAI_API_KEY`, or the uploaded file itself being corrupt/unsupported.
- **Chat tab returns a 502** → `GEMINI_API_KEY` missing/invalid, or
  you've hit Gemini's free-tier daily request cap. Everything else
  works without it.
- **Frontend can't reach the API at all (network error, not CORS)** →
  double check `NEXT_PUBLIC_API_URL` on Vercel is the exact Render URL,
  including `https://`.
