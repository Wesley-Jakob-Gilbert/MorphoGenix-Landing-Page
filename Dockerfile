# MorphoGenix landing page — production image
# Multi-stage build: slim runtime, no build toolchain in final layer.

# ---- Builder ----
FROM python:3.14-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Install only prod deps into a venv we can copy cleanly.
COPY requirements.txt .
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install \
        "fastapi>=0.118.3" \
        "uvicorn[standard]>=0.40.0" \
        "jinja2>=3.1.4" \
        "python-dotenv>=1.0.1" \
        "httpx>=0.27.2" \
        "pydantic[email]>=2.12.0"

# ---- Runtime ----
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    APP_ENV=production \
    PORT=8080

# Run as a non-root user.
RUN groupadd --system app && useradd --system --gid app --home /app app

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app app ./app

USER app

EXPOSE 8080

# Single worker is fine for a landing page + waitlist POST.
# uvicorn[standard] brings uvloop + httptools for performance.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips=*"]
