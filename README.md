# MorphoGenix Landing Page

Marketing site and beta waitlist for MorphoGenix.

**Live at:** [morphogenix.ai](https://morphogenix.ai)

## What it is

A single-page marketing site with a beta waitlist signup. Waitlist submissions are validated server-side and written directly to a Notion database. Deploys to Fly.io via GitHub Actions on push to `main` (after CI passes).

## Stack

- **Backend:** Python 3.12 + [FastAPI](https://fastapi.tiangolo.com/), served by `uvicorn`
- **Frontend:** a Jinja2 template with Tailwind CSS via CDN — no bundler, no Node.js build step
- **Data:** Notion API as the waitlist datastore (`app/notion_client.py`)
- **Hardening:** `slowapi` rate limiting keyed on the Fly-Client-IP header, `TrustedHostMiddleware` (with `/healthz` exempted for Fly health checks), Pydantic request validation
- **Hosting:** Fly.io (Docker image, `python:3.12-slim`)

## Development

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # then set NOTION_TOKEN
uvicorn app.main:app --reload --port 8000
```

The app runs without `NOTION_TOKEN` — submissions return `{"ok": true, "stored": false}` instead of persisting, which is convenient for UI work.

Local URLs:
- `http://localhost:8000` — landing page
- `http://localhost:8000/api/docs` — FastAPI auto-generated docs
- `http://localhost:8000/healthz` — health check

**Environment variables**

| Variable | Purpose |
|---|---|
| `NOTION_TOKEN` | Notion internal integration secret (required for persistence) |
| `NOTION_DATABASE_ID` | Target Notion database (default set in `.env.example`) |
| `APP_ENV` | `development` locally, `production` on Fly |

## Deployment

Continuous deployment via GitHub Actions. On push to `main`, the CI workflow (Ruff lint/format, Bandit, pip-audit, Gitleaks) runs; on success the deploy workflow ships the Docker image to Fly.io.

- **Production app:** `morphogenix-landing-page-1-2pra` (config: `fly.toml`, region `dfw`)
- **Staging app:** `morphogenix-staging` (config: `fly.staging.toml`, deploys from `staging`)

Do not run `fly launch` from the project root — it rewrites `app = ...` in `fly.toml` and can silently retarget production. Use `--config fly.<env>.toml` for new apps.

## Structure

```
app/
├── main.py            FastAPI app: routes, Pydantic models, middleware
├── notion_client.py   Async httpx wrapper for the Notion pages API
├── templates/
│   ├── index.html     Landing page: markup, Tailwind config, form handler
│   └── privacy.html   Privacy policy
└── static/            Served at /static/ (logo, app.js, styles, demo assets)
```

Routes: `GET /` (landing), `GET /privacy`, `POST /api/waitlist`, `GET /healthz`, `GET /demo`.

## Related

- Companion app + firmware: [morphogenix-app](https://github.com/Wesley-Jakob-Gilbert/morphogenix-app)
