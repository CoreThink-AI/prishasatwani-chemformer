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

# Install CUDA-capable torch first; torch==1.8.1+cu111 satisfies torch==1.8.1
# (PEP 440: local version segment +cu111 is ignored when not specified in the constraint)
RUN uv venv /venv \
 && uv pip install --python /venv/bin/python --no-cache \
      "torch==1.8.1+cu111" \
      --index-url https://download.pytorch.org/whl/cu111 \
 && uv pip install --python /venv/bin/python --no-cache ".[service]"


# ---- runtime stage ----
FROM nvidia/cuda:11.1.1-cudnn8-runtime-ubuntu20.04

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.8 \
    python3-distutils \
    libxrender1 \
    libxext6 \
 && rm -rf /var/lib/apt/lists/* \
 && ln -sf /usr/bin/python3.8 /usr/local/bin/python3.8 \
 && ln -sf /usr/bin/python3.8 /usr/local/bin/python3 \
 && ln -sf /usr/bin/python3.8 /usr/local/bin/python

# Non-root user required by Cloud Run security policy
RUN useradd --create-home --uid 1000 appuser

WORKDIR /app

COPY --from=builder /venv /venv
COPY --chown=appuser:appuser src/ ./src/

# Redirect venv Python symlinks to the runtime Python location.
# The builder used /usr/local/bin/python3.8 (python:3.8-slim); the CUDA
# Ubuntu image installs Python to /usr/bin/python3.8. We symlink
# /usr/local/bin/python3.8 above so pyvenv.cfg "home = /usr/local/bin" resolves.
RUN ln -sf /usr/bin/python3.8 /venv/bin/python3.8 \
 && ln -sf /usr/bin/python3.8 /venv/bin/python3 \
 && ln -sf /usr/bin/python3.8 /venv/bin/python

USER appuser

ENV PATH="/venv/bin:$PATH" \
    PYTHONPATH="/app/src" \
    PYTHONUNBUFFERED=1 \
    CHEMFORMER_N_GPUS=1

# Cloud Run injects PORT; default to 8080
EXPOSE 8080

CMD ["sh", "-c", \
     "uvicorn chemformer.service.retrosynthesis_service:app \
      --host 0.0.0.0 \
      --port ${PORT:-8080} \
      --workers 1"]
