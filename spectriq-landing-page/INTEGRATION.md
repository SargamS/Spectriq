# Spectriq — frontend/backend integration notes

This frontend now talks to the real FastAPI backend instead of using mock
data. Here's what changed and how to run the whole thing.

## What was wired up

- **`lib/api.ts`** — a typed client for every backend endpoint: upload,
  job status, list/get/update meeting, and chat (both non-streaming and
  SSE-streaming variants). All requests send a real Clerk session token
  as `Authorization: Bearer <token>`; the backend verifies it against
  Clerk's JWKS (`app/auth.py`) instead of trusting a client-supplied
  header. (Previously this was an `X-User-Email` header with no
  verification at all — that's gone.)
- **`app/page.tsx`** (landing) — pure marketing page now; it links to
  `/sign-in`, which is Clerk's own hosted-component sign-in flow (Google
  OAuth or email). There's no custom email/password form anymore — the
  old one collected a password but never checked it against anything.
- **`app/dashboard/page.tsx`** — real file upload via `POST /upload`
  (with progress), a real "Recent Meetings" list via `GET /meetings`,
  loading/error states, and sign-out via Clerk's `signOut()`.
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
# fill in at least OPENAI_API_KEY (summarization) — GEMINI_API_KEY is
# only needed if you want the chat-with-meeting tab to work; everything
# else works without it.
docker compose up --build
```

This starts Postgres+pgvector and the API (`localhost:8000`). The API
also runs the transcription/summarization pipeline in-process on a
background thread (see `app/background.py`) - there's no separate worker
to run.

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

## One-time Clerk setup (required before auth will work)

1. Create a free app at [clerk.com](https://clerk.com).
2. Frontend: set `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` and `CLERK_SECRET_KEY`
   in `.env.local` (from Clerk Dashboard → API Keys).
3. Backend: set `CLERK_JWKS_URL` in `.env` — it's your Clerk instance's
   Frontend API URL + `/.well-known/jwks.json` (Clerk Dashboard → API
   Keys → Advanced, or just append the path yourself).
4. Run the database migration below (`clerk_id` column) before your first
   real sign-in — the old `X-User-Email`-based `users` rows won't have one.

```sql
-- One-time migration: users are now keyed by Clerk's user id, not email.
ALTER TABLE users ADD COLUMN clerk_id VARCHAR;
ALTER TABLE users ALTER COLUMN email DROP NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ix_users_clerk_id ON users (clerk_id);
-- Old demo/stub rows (created via X-User-Email) have no clerk_id and are
-- now orphaned - safe to delete once you've confirmed real sign-in works:
-- DELETE FROM users WHERE clerk_id IS NULL;
```

## Known limitations to be aware of

- **No transcript speaker labels.** The backend's Whisper transcription
  doesn't do speaker diarization, so the transcript tab shows timestamped
  lines without speaker names. This was previously listed as a feature on
  the landing page ("Speaker Detection") — that claim has been removed
  since the feature doesn't exist yet; see the backend's `speaker_label`
  column (nullable, unpopulated) for where it would slot in.
- **Full pipeline needs one paid API key** (OpenAI, for summarization) —
  without it, uploads will fail at the summarization stage with a clear
  error message on the results page. The chat tab uses Gemini instead,
  which has a genuine free tier (no credit card required).

## Deploying to Render + Vercel

See `spectriq-backend/DEPLOY.md` for the full walkthrough (env vars,
the `render.yaml` blueprint). Short version:

- Backend goes on Render (free web service) — use the `render.yaml`
  blueprint in the backend folder (New -> Blueprint in the Render
  dashboard). The database is Neon (neon.com) instead of Render's own
  Postgres, since Neon's free tier is permanent (Render's expires after
  30 days) - see `spectriq-backend/DEPLOY.md` for the quick signup steps.
  No Redis or separate worker needed; the pipeline runs inside the same
  web service.
- Frontend goes on Vercel — set `NEXT_PUBLIC_API_URL` to your Render API
  URL.
- `STORAGE_BACKEND=local` (the default) is fine on Render now too, since
  the API and the pipeline are the same process/disk. Only switch to
  `s3` if you want uploaded files to survive across instance restarts.
