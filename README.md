# MorphoGenix — Landing Page + Beta Waitlist

A dark-tech, biometric-styled landing page for **MorphoGenix**, the first intraoral
biometric device for tongue posture, bruxism, and mouth breathing. Built with
**FastAPI + Jinja2 + Tailwind**. Waitlist signups are written directly to the
**MorphoGenix Beta Waitlist** database in your Notion workspace.

## What you get

```
morphogenix-web/
├── app/
│   ├── main.py              # FastAPI app: GET / (landing) + POST /api/waitlist
│   ├── notion_client.py     # Thin async Notion API client (httpx)
│   └── templates/
│       └── index.html       # The entire landing page (Tailwind via CDN, no build step)
├── requirements.txt
├── .env.example             # Copy to .env and fill in NOTION_TOKEN
└── README.md
```

Sections on the page:
1. **Hero** — "Your face is a mountain range shaped by millions of tiny signals."
2. **How it works** — 3-step: wear → stream BLE → see posture
3. **The science** — thresholds + live palate heatmap SVG
4. **Founder note + patents** — Wes Gilbert, Billion Dollar Build, Patent pending
5. **Waitlist form** — email, name, persona chips, optional "what pulled you in?"

## 1. First-time setup

### 1a. Install Python deps

```bash
cd morphogenix-web
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 1b. Create a Notion integration (one-time, ~2 minutes)

1. Open [https://www.notion.so/profile/integrations](https://www.notion.so/profile/integrations)
2. Click **New integration** → name it `MorphoGenix Web` → Associated workspace = your workspace → **Save**
3. Copy the **Internal Integration Secret** (starts with `secret_` or `ntn_`)
4. Open the **MorphoGenix Beta Waitlist** database page in Notion
   (already created inside *🦷 MorphoGenix — Billion Dollar Build HQ*)
5. Click the **⋯** menu (top right) → **Connections** → **Connect to** → pick *MorphoGenix Web*
   *(this is what gives your integration permission to write rows)*

### 1c. Configure environment

```bash
cp .env.example .env
```

Then edit `.env`:

```env
NOTION_TOKEN=secret_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
NOTION_DATABASE_ID=2fdab5cfd494473aa2d41d04e09ef6c0   # already set — this is your waitlist DB
```

## 2. Run it

```bash
uvicorn app.main:app --reload --port 8000
```

Open [http://localhost:8000](http://localhost:8000). Submit a test signup; it
should appear as a new row in the **MorphoGenix Beta Waitlist** database within
a second or two.

Interactive API docs (FastAPI gives you these for free): [http://localhost:8000/api/docs](http://localhost:8000/api/docs)

### Dev mode without Notion

If `NOTION_TOKEN` isn't set, the form still works — it accepts signups and
returns `{"ok": true, "stored": false}`. Useful for iterating on UI without
spamming your Notion DB.

## 3. How the Notion write works

`POST /api/waitlist` accepts JSON:

```json
{
  "email": "you@domain.com",
  "name": "Optional",
  "persona": "Mewer | Bruxism sufferer | Mouth breather | Clinician | Other",
  "reason": "Optional free text"
}
```

The server validates the payload with Pydantic (including email format), then
calls `notion_client.add_waitlist_signup()` which POSTs to Notion's
`/v1/pages` endpoint with your database as the parent. The title property is
`Email`, `Source` is auto-set to `Landing Page`, and `Status` starts at
`Not started`.

## 4. Design tokens

If you ever want to tweak the palette, it's all in the `tailwind.config` block
at the top of `app/templates/index.html`:

| Token      | Hex       | Use                                    |
|------------|-----------|----------------------------------------|
| `slatebg`  | `#0A0F14` | Page background (near-black slate)     |
| `slatebg2` | `#0F151C` | Alternating section background         |
| `slatecard`| `#111820` | Card surfaces                          |
| `ridge`    | `#1A2330` | Hairline borders / mountain "ridges"   |
| `neon`     | `#39FF9C` | Primary neon green (CTAs, "engaged")   |
| `electric` | `#3FA9FF` | Accent electric blue (data, links)     |
| `inkhi`    | `#E6F0EE` | High-emphasis text                     |
| `inklo`    | `#8A9AA6` | Low-emphasis text / captions           |

The topographic mountain contours in the hero and waitlist section are a
single inline SVG — no image asset to manage. You can swap it for a real
photo or a Perplexity-generated image later by replacing the `.topo`
`background-image` URL.

## 5. Deploying

The app is a vanilla ASGI app, so deploys anywhere that runs Python:

- **Render / Railway / Fly.io** — set build command `pip install -r requirements.txt`,
  start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, add
  `NOTION_TOKEN` and `NOTION_DATABASE_ID` as env vars.
- **Fly example:** `fly launch --no-deploy` then set secrets via `fly secrets set`.
- **Docker:** a one-file Dockerfile is 10 lines if you need it — ask and I'll add one.

## 6. Next things to wire up

- Custom domain (you budgeted ~$30 for domain + hosting)
- UTM tracking on the signup (`Source` column already supports Reddit/TikTok/Referral)
- Rate-limit the waitlist endpoint (slowapi is a one-liner)
- Swap the topo SVG for an AI-generated mountain image when you're ready

— Built during Billion Dollar Build, Week 2.
