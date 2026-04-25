"""MorphoGenix landing page + waitlist API.

Run locally:
    uvicorn app.main:app --reload --port 8000

Production is deployed on Fly.io — see fly.toml and Dockerfile. The rate
limiter keys on the Fly-Client-IP header (set by Fly's edge, not spoofable
by clients) rather than X-Forwarded-For (which clients can inject).
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from typing import Annotated

import httpx
from dotenv import load_dotenv
from fastapi import Body, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, EmailStr, Field
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware as _TrustedHostMiddleware
from starlette.types import Receive, Scope, Send

from .notion_client import NotionError, add_waitlist_signup


class TrustedHostMiddleware(_TrustedHostMiddleware):
    """TrustedHostMiddleware that exempts /healthz for Fly.io internal health checks.

    Fly's health checker hits the VM directly using its internal IP as the Host
    header, which would otherwise be rejected. /healthz carries no sensitive data
    so skipping host validation there is safe.
    """

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") == "http" and scope.get("path") == "/healthz":
            await self.app(scope, receive, send)
        else:
            await super().__call__(scope, receive, send)


load_dotenv()

# ---------- Config ----------
APP_ENV = os.environ.get("APP_ENV", "development").lower()
IS_PROD = APP_ENV == "production"

# Comma-separated list of hosts this app will answer for.
# Example: ALLOWED_HOSTS="morphogenix.ai,www.morphogenix.ai,morphogenix-landing.fly.dev"
_default_hosts = "morphogenix.ai,www.morphogenix.ai,*.fly.dev,localhost,127.0.0.1"
ALLOWED_HOSTS = [
    h.strip() for h in os.environ.get("ALLOWED_HOSTS", _default_hosts).split(",") if h.strip()
]

# Cloudflare Turnstile — optional bot protection.
TURNSTILE_SITE_KEY = os.environ.get("TURNSTILE_SITE_KEY", "")
TURNSTILE_SECRET_KEY = os.environ.get("TURNSTILE_SECRET_KEY", "")
TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

# ---------- Logging ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("morphogenix")


def _redact_email(email: str) -> str:
    """Return a non-reversible tag like 'ab***@example.com' for logging.

    Never log raw PII (email, name, reason) to stdout — on Fly that stream
    lands in a log aggregator with its own retention and is hard to purge
    for a GDPR subject-access request.
    """
    if not email or "@" not in email:
        return "<invalid>"
    local, _, domain = email.partition("@")
    prefix = local[:2] if len(local) >= 2 else local
    digest = hashlib.sha256(email.lower().encode()).hexdigest()[:8]
    return f"{prefix}***@{domain}#{digest}"


def _fly_client_ip(request: Request) -> str:
    """Return the real client IP using Fly's trusted Fly-Client-IP header.

    With --forwarded-allow-ips=* any client can spoof X-Forwarded-For and
    bypass the rate limiter. Fly sets Fly-Client-IP at the edge — it cannot
    be injected by the client. Falls back to the raw connection IP for local dev.
    """
    return request.headers.get("fly-client-ip") or (
        request.client.host if request.client else "unknown"
    )


# ---------- App ----------
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="MorphoGenix",
    # Hide interactive docs and the OpenAPI schema in production.
    docs_url=None if IS_PROD else "/api/docs",
    redoc_url=None,
    openapi_url=None if IS_PROD else "/openapi.json",
)

# Rate limiting keyed on Fly-Client-IP (not X-Forwarded-For, which clients can spoof).
limiter = Limiter(key_func=_fly_client_ip, default_limits=[])
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

# Reject requests with a Host header we don't serve (cache-poisoning hardening).
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={
            "ok": False,
            "message": "Too many requests. Please slow down and try again shortly.",
        },
    )


# Minimal security headers. CSP allows the Tailwind CDN + Turnstile script
# for now; tighten further once Tailwind is built locally.
_CSP_SCRIPT_SRC = "'self' https://cdn.tailwindcss.com https://challenges.cloudflare.com"
_CSP_FRAME_SRC = "https://challenges.cloudflare.com"
_CSP = (
    "default-src 'self'; "
    f"script-src {_CSP_SCRIPT_SRC}; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self' data:; "
    "connect-src 'self' https://challenges.cloudflare.com; "
    f"frame-src {_CSP_FRAME_SRC}; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "object-src 'none'"
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault(
        "Strict-Transport-Security",
        "max-age=63072000; includeSubDomains; preload",
    )
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resp.headers.setdefault(
        "Permissions-Policy",
        "geolocation=(), microphone=(), camera=(), interest-cohort=()",
    )
    resp.headers.setdefault("Content-Security-Policy", _CSP)
    return resp


# Make sure /static mount never crashes startup if the folder is missing
# (e.g. a fresh clone on a system that skipped empty dirs).
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def _notion_configured() -> bool:
    return bool(os.environ.get("NOTION_TOKEN") and os.environ.get("NOTION_DATABASE_ID"))


# ---------- Pages ----------
@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "notion_configured": _notion_configured(),
            "turnstile_site_key": TURNSTILE_SITE_KEY,
        },
    )


@app.get("/privacy")
async def privacy(request: Request):
    return templates.TemplateResponse(request, "privacy.html", {})


# ---------- Waitlist API ----------
class WaitlistSignup(BaseModel):
    email: EmailStr = Field(max_length=254)
    name: str | None = Field(default=None, max_length=120)
    reason: str | None = Field(default=None, max_length=600)
    persona: str | None = Field(default=None, max_length=40)
    # Honeypot — must stay empty. Humans never see this field.
    website: str | None = Field(default=None, max_length=200)
    # Cloudflare Turnstile token (optional; only enforced if TURNSTILE_SECRET_KEY is set).
    turnstile_token: str | None = Field(default=None, max_length=4096)
    # Client-reported ms between page load and submit. Used as a soft bot signal.
    elapsed_ms: int | None = Field(default=None, ge=0, le=24 * 60 * 60 * 1000)


ALLOWED_PERSONAS = {
    "Mewer",
    "Bruxism sufferer",
    "Mouth breather",
    "Clinician",
    "Other",
}


async def _verify_turnstile(token: str, client_ip: str | None) -> bool:
    """Verify a Turnstile token with Cloudflare. Returns True on success.

    If TURNSTILE_SECRET_KEY is unset, Turnstile is considered disabled and we
    return True (so local dev still works). In production, set the secret.
    """
    if not TURNSTILE_SECRET_KEY:
        return True
    if not token:
        return False
    data = {"secret": TURNSTILE_SECRET_KEY, "response": token}
    if client_ip:
        data["remoteip"] = client_ip
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(TURNSTILE_VERIFY_URL, data=data)
            body = resp.json()
        return bool(body.get("success"))
    except Exception as exc:  # noqa: BLE001 — fail closed, log no PII
        logger.warning("Turnstile verification error: %s", exc)
        return False


@app.post("/api/waitlist")
@limiter.limit("5/minute;20/hour")
async def waitlist(request: Request, signup: Annotated[WaitlistSignup, Body()]):
    # 1. Honeypot — bots fill every field; humans never see it.
    if signup.website:
        logger.info("Rejecting waitlist signup: honeypot filled (%s)", _redact_email(signup.email))
        # Return a 200 so bots don't learn this was a trap.
        return JSONResponse({"ok": True, "stored": False, "message": "Thanks."})

    # 2. Minimum time on page (very fast submits are almost always bots).
    if signup.elapsed_ms is not None and signup.elapsed_ms < 1500:
        logger.info(
            "Rejecting waitlist signup: too fast (%sms, %s)",
            signup.elapsed_ms,
            _redact_email(signup.email),
        )
        return JSONResponse({"ok": True, "stored": False, "message": "Thanks."})

    # 3. Turnstile (no-op if unconfigured).
    client_ip = _fly_client_ip(request)
    if not await _verify_turnstile(signup.turnstile_token or "", client_ip):
        logger.info("Rejecting waitlist signup: turnstile failed (%s)", _redact_email(signup.email))
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "message": "Human check failed. Please refresh and try again.",
            },
        )

    persona = signup.persona if signup.persona in ALLOWED_PERSONAS else None
    email_normalized = signup.email.lower().strip()

    # In production, silent data loss is unacceptable — fail loud.
    if not _notion_configured():
        if IS_PROD:
            logger.error(
                "Notion is not configured in production. Refusing signup (%s).",
                _redact_email(email_normalized),
            )
            return JSONResponse(
                status_code=503,
                content={
                    "ok": False,
                    "message": "Signups are temporarily unavailable. Please try again soon.",
                },
            )
        # Local dev affordance: accept the submission so the UX can be exercised,
        # but never log raw PII.
        logger.warning(
            "Dev-mode signup (Notion not configured): email=%s persona=%s",
            _redact_email(email_normalized),
            persona,
        )
        return JSONResponse(
            {
                "ok": True,
                "stored": False,
                "message": "Signup received (Notion not configured — not persisted).",
            }
        )

    try:
        await add_waitlist_signup(
            email=email_normalized,
            name=signup.name,
            reason=signup.reason,
            persona=persona,
            source="Landing Page",
        )
    except NotionError as exc:
        logger.exception(
            "Failed to write signup to Notion for %s: %s",
            _redact_email(email_normalized),
            exc,
        )
        return JSONResponse(
            status_code=502,
            content={
                "ok": False,
                "message": "We couldn't save your signup right now. Please try again.",
            },
        )

    return {"ok": True, "stored": True, "message": "You're on the list."}


@app.get("/healthz")
async def healthz():
    return {"ok": True}
