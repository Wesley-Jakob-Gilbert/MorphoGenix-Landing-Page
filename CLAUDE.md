# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MorphoGenix is a landing page with a beta waitlist signup. The backend is Python/FastAPI; the frontend is a single Jinja2 template using Tailwind CSS via CDN (no build step, no Node.js). Notion serves as the database — signups are written directly to a Notion database via the Notion API.

## Development Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # then fill in NOTION_TOKEN
uvicorn app.main:app --reload --port 8000
```

The app runs without `NOTION_TOKEN` set — form submissions return `{"ok": true, "stored": false}` instead of persisting, which is useful for UI work.

## Key URLs (local)

- `http://localhost:8000` — landing page
- `http://localhost:8000/api/docs` — FastAPI auto-generated docs
- `http://localhost:8000/healthz` — health check

## Environment Variables

| Variable | Purpose |
|---|---|
| `NOTION_TOKEN` | Notion internal integration secret (required for persistence) |
| `NOTION_DATABASE_ID` | Target Notion database; default is already set in `.env.example` |
| `APP_ENV` | Set to `development` for local use |

To obtain `NOTION_TOKEN`: create an internal integration at notion.so/profile/integrations, then connect it to the "MorphoGenix Beta Waitlist" database via the ⋯ menu → Connections.

## Architecture

```
app/
  main.py           # FastAPI app: routes, Pydantic models, startup logic
  notion_client.py  # Thin async httpx wrapper for Notion /v1/pages API
  templates/
    index.html      # Entire frontend: markup, Tailwind config, vanilla JS form handler
  static/           # Auto-created on startup (served as /static/)
```

**Data flow:** `POST /api/waitlist` → Pydantic `WaitlistSignup` validation → `notion_client.add_waitlist_signup()` → Notion API.

**Pydantic model constraints** (`WaitlistSignup` in `main.py`):
- `email` — required, EmailStr
- `name` — optional, max 120 chars
- `reason` — optional, max 600 chars
- `persona` — optional, max 40 chars, must be in `ALLOWED_PERSONAS`

**Notion errors** (`NotionError`) are caught in the route handler and return a 502 with detail.

## Frontend

`index.html` has no framework or bundler — all styling is Tailwind via CDN with custom design tokens declared in the `tailwind.config` block. Custom tokens:

| Token | Value | Role |
|---|---|---|
| `slatebg` | `#0A0F14` | page background |
| `neon` | `#39FF9C` | primary green accent |
| `electric` | `#3FA9FF` | secondary blue accent |
| `inkhi` | `#E6F0EE` | high-emphasis text |
| `inklo` | `#8A9AA6` | low-emphasis text |

Form submission uses `fetch` with JSON; the JS handles success/error states inline.

## Linting

```bash
ruff check app/          # check for issues
ruff check app/ --fix    # auto-fix what ruff can
ruff format app/         # format (black-compatible)
```

Config is in `ruff.toml`. Rules enabled: pycodestyle (E/W), pyflakes (F), isort (I), pyupgrade (UP).

## No Test Infrastructure

There are no automated tests or CI configuration in this repo.
