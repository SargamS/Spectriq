"""
FastAPI application entrypoint.

Run locally with:
    uvicorn app.main:app --reload

(the meeting-processing pipeline runs in-process on a background thread -
see app/background.py and app/workers/tasks.py - there's no separate
worker process to run.)
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
from app.db import Base, engine
from app.routes import chat, jobs, meetings, upload

app = FastAPI(
    title="Spectriq API",
    description="AI meeting summarizer backend",
    version="1.0.0",
)

# --- CORS ---
# Origins come from the ALLOWED_ORIGINS env var (comma-separated) so the
# Vercel frontend domain is never hardcoded here.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routers ---
app.include_router(upload.router)
app.include_router(jobs.router)
app.include_router(meetings.router)
app.include_router(chat.router)


@app.on_event("startup")
def on_startup():
    # The "chat with meeting" feature stores embeddings in a pgvector
    # column, so the extension must exist before create_all() runs (it
    # needs to resolve the `vector` type to build the transcript_chunks
    # table/index). Requires the pgvector/pgvector Postgres image (or the
    # pgvector extension installed some other way) - see docker-compose.yml.
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()

    # Creates tables if they don't exist yet. Fine for local dev / a
    # simple deployment; swap for Alembic migrations once the schema
    # needs to evolve safely against a live database.
    Base.metadata.create_all(bind=engine)


@app.get("/health", tags=["health"])
def health_check():
    """
    Lightweight liveness endpoint - used by Render/Railway health checks
    and to keep the service warm and combat cold starts. Deliberately
    does NOT touch the DB so it stays fast and always-green even if a
    downstream dependency hiccups.
    """
    return {"status": "ok"}
