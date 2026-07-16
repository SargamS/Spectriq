"""
Application configuration, loaded from environment variables (.env in local dev).
Uses pydantic-settings so values are validated and typed at startup.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- Database ---
    DATABASE_URL: str = "postgresql+psycopg2://spectriq:spectriq@localhost:5432/spectriq"

    # (Redis/Celery removed - the pipeline now runs in-process on a
    # background thread; see app/background.py.)

    # --- OpenAI ---
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"

    # --- CORS ---
    # Comma-separated list of allowed origins, e.g. "https://spectriq.vercel.app,https://spectriq-staging.vercel.app"
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    # --- Uploads ---
    MAX_UPLOAD_SIZE_MB: int = 500
    STORAGE_DIR: str = "/data/storage"  # mounted volume in docker-compose

    # --- File storage backend ---
    # "local" (default, and now the recommended setting): saves to
    # STORAGE_DIR on disk. This is safe again now that the API and the
    # background pipeline run in the same process (see app/background.py) -
    # they always share a filesystem, unlike the old separate-worker setup.
    # "s3": saves to an S3-compatible bucket (AWS S3, Cloudflare R2,
    # Backblaze B2, DigitalOcean Spaces, MinIO...). Only worth setting up
    # if you want uploaded files to persist beyond a single instance's
    # lifetime/restarts - not required for the pipeline to work.
    STORAGE_BACKEND: str = "local"
    S3_BUCKET: str = ""
    S3_REGION: str = "auto"
    S3_ENDPOINT_URL: str = ""       # leave blank for AWS S3; set for R2/B2/Spaces/MinIO
    S3_ACCESS_KEY_ID: str = ""
    S3_SECRET_ACCESS_KEY: str = ""

    # --- Whisper ---
    WHISPER_MODEL_SIZE: str = "base"
    WHISPER_DEVICE: str = "cpu"          # "cuda" if a GPU worker is available
    WHISPER_COMPUTE_TYPE: str = "int8"   # good CPU default for faster-whisper

    # --- Gemini (Google AI) - embeddings + chat, both used for "chat with
    # meeting". Both have a genuine free tier (no credit card required),
    # which is why they replaced Voyage AI + Anthropic here.
    GEMINI_API_KEY: str = ""
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-001"
    GEMINI_EMBEDDING_DIM: int = 768  # output_dimensionality requested from the embedding call
    GEMINI_CHAT_MODEL: str = "gemini-2.5-flash"

    # --- RAG chunking ---
    CHUNK_TARGET_WORDS: int = 300
    CHUNK_OVERLAP_WORDS: int = 50
    CHAT_TOP_K_CHUNKS: int = 5

    # --- Chat rate limiting ---
    CHAT_RATE_LIMIT_PER_HOUR: int = 20

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    # cached so we don't re-parse env vars on every import
    return Settings()


settings = get_settings()
