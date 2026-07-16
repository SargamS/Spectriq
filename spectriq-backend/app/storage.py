"""
Storage abstraction for uploaded files.

Two backends, chosen via STORAGE_BACKEND:

  - "local" (default): saves to STORAGE_DIR on disk. Safe as long as the
    API process and the background pipeline thread share a filesystem -
    true now that both run in the same process (see app/background.py).

  - "s3": saves to an S3-compatible bucket (AWS S3, Cloudflare R2,
    Backblaze B2, DigitalOcean Spaces, MinIO...). Only needed if you
    want uploads to persist beyond a single instance's lifetime. The API
    uploads the file and stores a reference to it; the pipeline
    downloads its own local copy of that file before running
    ffmpeg/Whisper on it (those tools need a real local path, not a
    remote key).

Callers only depend on `save_upload` (called by the API on upload) and
`fetch_local_copy` (called before processing) - neither needs to know
which backend is active.
"""
import os
import uuid

from app.config import settings


class StorageError(Exception):
    pass


def _local_dir() -> str:
    d = os.path.join(settings.STORAGE_DIR, "uploads")
    os.makedirs(d, exist_ok=True)
    return d


def _s3_client():
    # Imported lazily so boto3 isn't required at all when running with
    # the local backend (e.g. simple docker-compose dev).
    import boto3
    from botocore.client import Config as BotoConfig

    if not settings.S3_BUCKET:
        raise StorageError(
            "STORAGE_BACKEND=s3 but S3_BUCKET is not set. Also set "
            "S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY, and S3_ENDPOINT_URL "
            "(leave S3_ENDPOINT_URL blank if using real AWS S3)."
        )
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL or None,
        aws_access_key_id=settings.S3_ACCESS_KEY_ID or None,
        aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY or None,
        region_name=settings.S3_REGION or None,
        config=BotoConfig(signature_version="s3v4"),
    )


def save_upload(file_obj, original_filename: str) -> str:
    """
    Persists an uploaded file (streamed in 1MB chunks so large videos
    never load fully into memory) and returns a storage reference:
      - local backend: an absolute local path
      - s3 backend: an "s3://<bucket>/<key>" URI

    This reference is what gets stored on Meeting.source_path. Whoever
    needs to actually read the file later (the Celery worker) must call
    `fetch_local_copy` on it first.
    """
    ext = os.path.splitext(original_filename)[1].lower()
    unique_name = f"{uuid.uuid4().hex}{ext}"

    if settings.STORAGE_BACKEND == "s3":
        key = f"uploads/{unique_name}"
        client = _s3_client()
        try:
            client.upload_fileobj(file_obj, settings.S3_BUCKET, key)
        except Exception as exc:
            raise StorageError(f"Failed to upload to S3: {exc}") from exc
        return f"s3://{settings.S3_BUCKET}/{key}"

    dest_path = os.path.join(_local_dir(), unique_name)
    with open(dest_path, "wb") as out:
        while chunk := file_obj.read(1024 * 1024):
            out.write(chunk)
    return dest_path


def fetch_local_copy(reference: str, work_dir: str) -> str:
    """
    Given whatever `save_upload` returned, guarantees a local copy of
    the file exists on *this* machine and returns its local path.

    - s3 reference ("s3://bucket/key"): downloads the object into
      work_dir and returns that path.
    - local reference (a plain path): returned as-is, since the local
      backend only works when caller and creator share a disk. Raises
      a clear error if the path doesn't actually exist here, which is
      the exact symptom of "API and worker are on separate machines but
      STORAGE_BACKEND is still 'local'".
    """
    if reference.startswith("s3://"):
        _, _, rest = reference.partition("s3://")
        bucket, _, key = rest.partition("/")
        os.makedirs(work_dir, exist_ok=True)
        local_path = os.path.join(work_dir, os.path.basename(key))
        client = _s3_client()
        try:
            client.download_file(bucket, key, local_path)
        except Exception as exc:
            raise StorageError(f"Failed to download {reference} from S3: {exc}") from exc
        return local_path

    if not os.path.exists(reference):
        raise StorageError(
            f"Local file not found: {reference}. If the API and worker are "
            f"separate services/machines, set STORAGE_BACKEND=s3 (with "
            f"S3_BUCKET/S3_ACCESS_KEY_ID/S3_SECRET_ACCESS_KEY) instead of "
            f"'local' so uploaded files can actually be shared between them."
        )
    return reference


def delete_local_copy(local_path: str) -> None:
    """Best-effort cleanup of a temp copy downloaded via fetch_local_copy."""
    try:
        if os.path.exists(local_path):
            os.remove(local_path)
    except OSError:
        pass


def resolve_path(path: str) -> str:
    return path
