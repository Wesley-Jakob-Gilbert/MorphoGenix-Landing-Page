"""MorphoGenix landing page + waitlist API.

Run locally:
    uvicorn app.main:app --reload --port 8000
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, EmailStr, Field

from .notion_client import NotionError, add_waitlist_signup

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("morphogenix")

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="MorphoGenix", docs_url="/api/docs", redoc_url=None)

app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static",
)
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# ---------- Landing page ----------
@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "notion_configured": bool(
                os.environ.get("NOTION_TOKEN")
                and os.environ.get("NOTION_DATABASE_ID")
            ),
        },
    )


# ---------- Waitlist API ----------
class WaitlistSignup(BaseModel):
    email: EmailStr
    name: Optional[str] = Field(default=None, max_length=120)
    reason: Optional[str] = Field(default=None, max_length=600)
    persona: Optional[str] = Field(default=None, max_length=40)


ALLOWED_PERSONAS = {
    "Mewer",
    "Bruxism sufferer",
    "Mouth breather",
    "Clinician",
    "Other",
}


@app.post("/api/waitlist")
async def waitlist(signup: WaitlistSignup):
    persona = signup.persona if signup.persona in ALLOWED_PERSONAS else None

    # If Notion is not configured (local dev without secrets), log and succeed
    # so the frontend UX can still be exercised.
    if not (os.environ.get("NOTION_TOKEN") and os.environ.get("NOTION_DATABASE_ID")):
        logger.warning(
            "Waitlist signup received but Notion is not configured. "
            "Signup: email=%s name=%s persona=%s",
            signup.email,
            signup.name,
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
            email=signup.email,
            name=signup.name,
            reason=signup.reason,
            persona=persona,
            source="Landing Page",
        )
    except NotionError as exc:
        logger.exception("Failed to write signup to Notion: %s", exc)
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
