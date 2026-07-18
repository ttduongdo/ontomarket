# OntoMarket API — Fly.io deploy image (Python backend only; the React
# front-end deploys separately to Vercel).

FROM python:3.11-slim

# Bake the sentence-transformers model into the image at build time so the
# container never downloads it at runtime (no cold-start network dependency).
ENV HF_HOME=/models \
    SENTENCE_TRANSFORMERS_HOME=/models \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps: sentence-transformers/torch need libgomp at runtime.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first (layer caching — only re-runs when deps change).
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

# Pre-download the embedding model into the image.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# App code + the data the API reads (processed graph + snippets for Chroma rebuild).
COPY src/ ./src/
COPY api/ ./api/
COPY data/ ./data/

# Fly injects $PORT (default 8080). Bind there; single worker (the model is
# loaded once at startup and is not fork-safe across workers cheaply).
ENV PORT=8080
EXPOSE 8080
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT}"]
