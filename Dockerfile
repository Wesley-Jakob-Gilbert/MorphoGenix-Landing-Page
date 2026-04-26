# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Non-root user
RUN useradd --create-home --uid 10001 app
WORKDIR /app

# Install deps first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Cache-busting arg so the COPY layer is never reused across deploys.
# The CD workflow passes a fresh value on every build; locally it just
# defaults to "dev". Without this, BuildKit can spuriously hit cache on
# `COPY app` even when the source actually changed.
ARG BUILD_MARKER=dev
ENV BUILD_MARKER=${BUILD_MARKER}
RUN echo "build=${BUILD_MARKER}"

# App code
COPY app ./app

USER 10001
EXPOSE 8080

# --proxy-headers + --forwarded-allow-ips lets uvicorn (and our rate limiter)
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8080", \
     "--proxy-headers", \
     "--forwarded-allow-ips=*"]
