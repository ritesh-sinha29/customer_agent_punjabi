# Stage 1: Build dependencies
FROM python:3.13-slim AS builder

# Install uv using the official binary from Github releases
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Disable telemetry and set environment configurations
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Run uv sync mounting cache and dependencies to avoid unnecessary downloads
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    /bin/uv sync --frozen --no-install-project --no-dev

# Stage 2: Runtime
FROM python:3.13-slim

# Install system dependencies if required (e.g. git, libcurl, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the virtual environment from the builder
COPY --from=builder /app/.venv /app/.venv

# Update the environment path to default to the virtual environment
ENV PATH="/app/.venv/bin:$PATH"

# Copy source code and files
COPY src /app/src
COPY main.py /app/main.py

# Expose FastAPI default port
EXPOSE 8000

# Start app
CMD ["uvicorn", "src.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
