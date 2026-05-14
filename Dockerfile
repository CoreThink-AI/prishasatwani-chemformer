# ---- build stage ----
FROM python:3.8-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    libxrender1 \
    libxext6 \
 && rm -rf /var/lib/apt/lists/*

# Install uv from its official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /build
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Create venv and install project + service extras via uv
RUN uv venv /venv \
 && uv pip install --python /venv/bin/python --no-cache ".[service]"


# ---- runtime stage ----
FROM python:3.8-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libxrender1 \
    libxext6 \
 && rm -rf /var/lib/apt/lists/*

# Non-root user required by Cloud Run security policy
RUN useradd --create-home --uid 1000 appuser

WORKDIR /app

COPY --from=builder /venv /venv
COPY --chown=appuser:appuser src/ ./src/

USER appuser

ENV PATH="/venv/bin:$PATH" \
    PYTHONPATH="/app/src" \
    PYTHONUNBUFFERED=1 \
    CHEMFORMER_N_GPUS=0

# Cloud Run injects PORT; default to 8080
EXPOSE 8080

CMD ["sh", "-c", \
     "uvicorn chemformer.service.retrosynthesis_service:app \
      --host 0.0.0.0 \
      --port ${PORT:-8080} \
      --workers 1"]
