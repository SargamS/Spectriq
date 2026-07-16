# Deploying the Spectriq backend to Render

## What gets created

Using the included `render.yaml` blueprint, Render creates 4 things in
one shot:

1. **spectriq-db** — Postgres (with pgvector) — the database
2. **spectriq-redis** — Redis — Celery's job queue + chat rate limiter
3. **spectriq-api** — Web Service — the FastAPI app, handles HTTP requests
4. **spectriq-worker** — Background Worker — same code, runs the Celery
   pipeline (audio extraction -> transcription -> summarization -> indexing)

## Step 1 — Choose a file storage option

The API (which receives uploads) and the worker (which processes them)
are **separate services on separate machines**. They do not share a
disk. So you need real object storage, not local disk. Pick one:

- **Cloudflare R2** — S3-compatible, no egress fees, generous free tier.
  Recommended default.
- **AWS S3** — the original; leave `S3_ENDPOINT_URL` blank if you use this.
- **Backblaze B2** or **DigitalOcean Spaces** — also S3-compatible, also fine.

Whichever you pick, create a bucket and an access key pair, then note:
- Bucket name
- Access key ID / secret access key
- Endpoint URL (blank for real AWS S3; required for the others, e.g.
  `https://<account-id>.r2.cloudflarestorage.com` for R2)
- Region (R2 uses `auto`; others use their real region name)

## Step 2 — Get your API keys

- **OpenAI** (required) — platform.openai.com — used for the actual
  meeting summary.
- **Gemini / Google AI** (optional) — aistudio.google.com — only needed
  for the "chat with meeting" tab (used for both embeddings and the chat
  answers). Has a genuine free tier with no credit card required.

## Step 3 — Deploy via Blueprint

1. Push this `spectriq` folder to a GitHub repo (it needs to be the
   repo root, or set as the root directory Render points at).
2. In the Render dashboard: **New -> Blueprint**, pick that repo.
   Render reads `render.yaml` and shows you a preview of the 4 things
   above.
3. Click **Apply**. Wait for everything to build (the first build is
   slow — it's installing ffmpeg, faster-whisper, and downloading the
   Whisper model weights).
4. Once created, go into **spectriq-api** and **spectriq-worker**'s
   "Environment" tabs and fill in the values marked `sync: false` in
   `render.yaml` — your real API keys and S3 credentials. Both services
   need the same S3 credentials (one uploads, one downloads).
5. Open **spectriq-db**'s Shell tab once and run:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
   (the app also tries this on its own startup, so this is just a
   safety net in case of a timing race on the very first deploy.)

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

## Troubleshooting

- **Uploads stuck on "queued" forever** → the worker never picked up
  the job. Check the worker's logs in Render — likely `REDIS_URL`
  mismatch between the two services, or the worker crashed on startup.
- **Uploads fail at "extracting audio"** → almost always
  `STORAGE_BACKEND` is still `local`, or the S3 credentials are wrong/
  missing on the worker specifically (it's the one that needs to
  download the file back down).
- **Chat tab returns a 502** → `VOYAGE_API_KEY` or `ANTHROPIC_API_KEY`
  missing/invalid. Everything else works without them.
- **Frontend can't reach the API at all (network error, not CORS)** →
  double check `NEXT_PUBLIC_API_URL` on Vercel is the exact Render URL,
  including `https://`.
