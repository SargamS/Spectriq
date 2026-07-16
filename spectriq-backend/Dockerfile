# Base image for the API, which also runs the processing pipeline
# in-process on a background thread (see app/background.py) - no
# separate worker image needed.
FROM python:3.11-slim

# ffmpeg is required for audio extraction; git is needed by some pip
# packages that build from source.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /code

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Storage volume for uploaded/processed media - mounted via docker-compose.
RUN mkdir -p /data/storage

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
