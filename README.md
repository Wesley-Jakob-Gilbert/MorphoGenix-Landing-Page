# MorphoGenix — Landing Page + Beta Waitlist

Dark-tech, biometric-styled landing page for **MorphoGenix**, the first
intraoral biometric device for tongue posture, bruxism, and mouth breathing.

- **Stack:** FastAPI · Jinja2 · Tailwind (compiled config) · Three.js hero
- **Hosting:** [Fly.io](https://fly.io) — `dfw` region, single always-on
  shared-cpu-1x machine, auto-renewing TLS
- **Storage:** waitlist signups written directly to the **MorphoGenix Beta
  Waitlist** Notion database via the Notion REST API
- **Live:** [morphogenix.ai](https://morphogenix.ai) *(custom domain handoff in progress)*
  · fallback [morphogenix-landing-page-1-2pra.fly.dev](https://morphogenix-landing-page-1-2pra.fly.dev)
- **CI/CD:** GitHub Actions — every push to `main` runs lint + security scans
  and (on success) auto-deploys to Fly

## Repo layout

```
MorphoGenix-Landing-Page/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app, security middleware, /api/waitlist
│   ├── notion_client.py         # Async Notion API client (httpx)
│   ├── static/
│   │   ├── app.js               # Form submit, Turnstile, fetch logic
│   │   ├── tailwind.config.js   # Tailwind config (loaded as a static file for CSP)
│   │   └── privacy.css
│   └── templates/
│       ├── index.html           # Landing page (hero, How it works, Science, Founder, Waitlist)
│       └── privacy.html         # /privacy page (linked from the consent checkbox)
├── .github/workflows/
│   ├── ci.yml                   # ruff · bandit · pip-audit · gitleaks
│   └── deploy.yml               # Auto-deploy to Fly.io on green CI
├── Dockerfile                   # python:3.12-slim, non-root user, port 8080
├── fly.toml                     # Fly.io app config
├── requirements.txt             # Pinned runtime + dev deps
├── ruff.toml                    # Lint config
├── .env.example                 # Template for local development
├── TODO.md
└── CLAUDE.md
```

Sections on the landing page:

1. **Hero** — Three.js 3D viewer of the device, pulsing rotation, tagline
2. **How it works** — wear → stream BLE → see posture
3. **The science** — palate heatmap SVG, threshold callouts
4. **Founder note + patents** — Wes Gilbert, Billion Dollar Build, patent pending
5. **Waitlist form** — email, name, persona chips, optional reason, consent + privacy link, Cloudflare Turnstile widget

## 1. Local development

### 1a. Install Python deps

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 1b. Create a Notion integration (one-time, ~2 min)

1. Open <https://www.notion.so/profile/integrations>
2. **New integration** → name `MorphoGenix Web` → save
3. Copy the **Internal Integration Secret**
4. Open the **MorphoGenix Beta Waitlist** database in Notion → **⋯** menu →
   **Connections** → connect the integration *(this grants write access)*

### 1c. Configure environment

```bash
cp .env.example .env
```

Then fill in `.env`:

```env
NOTION_TOKEN=secret_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
NOTION_DATABASE_ID=2fdab5cfd494473aa2d41d04e09ef6c0
APP_ENV=development
```

Optional (only needed if you want to test bot protection locally):

```env
TURNSTILE_SITE_KEY=0xAAAA...
TURNSTILE_SECRET_KEY=0xAAAA...
```

If `TURNSTILE_SECRET_KEY` is unset, server-side verification is bypassed and
all submissions are accepted as human. This is the intended local-dev fallback.

### 1d. Run

```bash
uvicorn app.main:app --reload --port 8000
```

Open <http://localhost:8000>. Submit a test signup; a new row should land in
the **MorphoGenix Beta Waitlist** database within a second.

In **development** (`APP_ENV=development`), interactive API docs are at
<http://localhost:8000/api/docs>. They are **disabled in production**.

### Dev mode without Notion

If `NOTION_TOKEN` is unset, the form still works — it accepts signups and
returns `{"ok": true, "stored": false}`. Useful for UI iteration without
spamming the real Notion DB.

## 2. POST /api/waitlist

JSON body (validated with Pydantic v2):

```json
{
  "email":           "you@domain.com",
  "name":            "Optional",
  "persona":         "Mewer | Bruxism sufferer | Mouth breather | Clinician | Other",
  "reason":          "Optional free text",
  "website":         "",
  "turnstile_token": "<token from Cloudflare widget>",
  "elapsed_ms":      5234,
  "consent":         true
}
```

Bot-protection layers applied in order:

1. **Honeypot** — `website` is hidden from humans via CSS. Any non-empty
   value silently rejects the request (returns a fake-success 200 so bots
   don't learn the field is a trap).
2. **Min-time check** — `elapsed_ms < 1500` is rejected. Humans can't fill
   the form in under 1.5 s; many bots can.
3. **Rate limiting** — slowapi: `5/minute;20/hour` per IP on `/api/waitlist`.
4. **Cloudflare Turnstile** — `turnstile_token` is verified server-side
   against `https://challenges.cloudflare.com/turnstile/v0/siteverify`.
   Bypassed when `TURNSTILE_SECRET_KEY` is unset (local dev).
5. **Consent gate** — `consent: true` is required and explicit; the privacy
   policy is linked next to the checkbox.

After validation, the row is written to Notion with these properties:

- `Email` *(title)*
- `Name` *(rich_text)*
- `Persona` *(select)*
- `Reason for Interest` *(rich_text)*
- `Source` *(select, default `Landing Page`)*
- `Status` *(status, default `Not started`)*

## 3. Security & infra (what's actually running)

- **TLS:** Fly-managed certs, force-https
- **Headers:** HSTS (2-year preload), CSP, `X-Frame-Options: DENY`,
  `X-Content-Type-Options: nosniff`, Referrer-Policy, Permissions-Policy
- **`TrustedHostMiddleware`** locks the `Host` header to allowed domains
  (configurable via `ALLOWED_HOSTS` env). `/healthz` is exempted so Fly's
  internal health checks pass.
- **`/api/docs` and `/openapi.json`** are hidden in production (`APP_ENV=production`)
- **CI** (`.github/workflows/ci.yml`) runs on every PR and push:
  `ruff check` · `bandit` · `pip-audit` · `gitleaks`
- **CD** (`.github/workflows/deploy.yml`) auto-deploys to Fly after CI passes
  on `main`. Trigger manual redeploys via *Actions → Deploy to Fly.io →
  Run workflow*.
- **Container:** `python:3.12-slim`, runs as UID 10001 (non-root),
  exposes port 8080, started with
  `uvicorn ... --proxy-headers --forwarded-allow-ips=*`.

## 4. Design tokens

Edit in `app/static/tailwind.config.js`:

| Token       | Hex       | Use                                    |
|-------------|-----------|----------------------------------------|
| `slatebg`   | `#0A0F14` | Page background (near-black slate)     |
| `slatebg2`  | `#0F151C` | Alternating section background         |
| `slatecard` | `#111820` | Card surfaces                          |
| `ridge`     | `#1A2330` | Hairline borders / mountain "ridges"   |
| `neon`      | `#39FF9C` | Primary neon green (CTAs, "engaged")   |
| `electric`  | `#3FA9FF` | Accent electric blue (data, links)     |
| `inkhi`     | `#E6F0EE` | High-emphasis text                     |
| `inklo`     | `#8A9AA6` | Low-emphasis text / captions           |

The topographic mountain contours and palate heatmap are inline SVGs — no
image assets to manage.

## 5. Deployment

### One-time Fly setup

```bash
fly launch --no-deploy            # generates the app + machine
fly secrets set NOTION_TOKEN=secret_... NOTION_DATABASE_ID=2fdab5cfd...
fly secrets set TURNSTILE_SITE_KEY=0x... TURNSTILE_SECRET_KEY=0x...
fly secrets set ALLOWED_HOSTS=morphogenix.ai,www.morphogenix.ai,morphogenix-landing-page-1-2pra.fly.dev
fly certs add morphogenix.ai
fly certs add www.morphogenix.ai
```

### Continuous deployment

Once `FLY_API_TOKEN` is set as a GitHub Actions repository secret
(generate with `fly tokens create deploy -x 999999h`), every push to
`main` that passes CI auto-deploys. Manual deploys still work via:

```bash
fly deploy --remote-only
```

### Custom domain (GoDaddy → Fly)

Point an A and AAAA record for the apex (`morphogenix.ai`) and a CNAME for
`www` to the Fly IPs printed by `fly ips list`. Cert issuance is automatic;
verify with `fly certs show morphogenix.ai`.

## 6. Roadmap

Already shipped (Week 2):

- ✅ Live deploy on Fly.io
- ✅ Notion-backed waitlist with full Pydantic validation
- ✅ Three.js 3D hero with blueprint cross-sections
- ✅ Rate limiting + honeypot + min-time + Turnstile + consent
- ✅ Hardened security headers + TrustedHost
- ✅ CI (lint + 3 security scanners)
- ✅ CD on push to `main`

Pre-announce checklist:

- ⏳ Custom domain `morphogenix.ai` cert `Issued`
- ⏳ End-to-end form smoke test from the custom domain
- ⏳ Cloudflare Turnstile widget verified live
- 🟡 (Optional) Sentry DSN for error tracking
- 🟡 (Optional) UptimeRobot ping on `/healthz`
- 🟡 (Optional) Email autoresponder from `privacy@morphogenix.ai`

Post-announce backlog:

- UTM parsing → `Source` column (Reddit / LinkedIn / Referral)
- Privacy-respecting analytics (Plausible) — decision pending
- Notion DB scheduled export / backup

— Built during the [Perplexity Billion Dollar Build](https://perplexity.ai), Week 2.

<!-- Build trigger: 2026-04-25T19:44:13Z -->
