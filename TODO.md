# MorphoGenix — Deployment & Ops TODO

Tracking open items for the Fly.io launch. Goal: hands-off from deploy through
at least June 2026. Items are grouped by priority; each PR suggestion is
self-contained and can be implemented independently.

---

## Status snapshot

| Item | State |
|---|---|
| PR #1 `devops/production-hardening` | Ready to merge |
| Fly.io deploy | Not yet done |
| Domain (morphogenix.ai) | Secured on GoDaddy |
| `privacy@morphogenix.ai` email | Done |

---

## P1 -- Required before first deploy

These are manual steps, not PRs. Someone must do them before `fly deploy`.

- [ ] **Create Fly.io app** -- `fly apps create morphogenix-landing`
- [ ] **Set Fly secrets** (never commit these):
      ```
      fly secrets set \
        NOTION_TOKEN=secret_... \
        NOTION_DATABASE_ID=... \
        TURNSTILE_SECRET_KEY=...
      ```
- [ ] **Set TURNSTILE_SITE_KEY in fly.toml** — uncomment the line, paste the
      public site key (safe to commit, visible in browser)
- [ ] **Tighten ALLOWED_HOSTS** — once the app name is confirmed, set the
      `ALLOWED_HOSTS` env var to `morphogenix.ai,www.morphogenix.ai,morphogenix-landing.fly.dev`
      instead of the wildcard `*.fly.dev` default
- [ ] **Point DNS to Fly** — `fly certs add morphogenix.ai www.morphogenix.ai`
      then set CNAME/A records in GoDaddy as instructed

---

## P1 — Error monitoring (open a new PR)

**Why:** Without this, production failures are invisible until a user complains.

**Suggested implementation:**
1. Add `sentry-sdk[fastapi]>=2.0.0` to `requirements.txt`
2. In `app/main.py`, after `load_dotenv()`:
   ```python
   import sentry_sdk
   sentry_sdk.init(
       dsn=os.environ.get("SENTRY_DSN", ""),
       environment=APP_ENV,
       traces_sample_rate=0.1,
   )
   ```
3. Run `fly secrets set SENTRY_DSN=https://...@sentry.io/...`
4. Sentry free tier captures 5,000 errors/month — sufficient for this scale.

Sentry will alert on: Notion 502s, unhandled exceptions, startup failures.

---

## P1 — Continuous deployment (open a new PR)

**Why:** Without CD, every deploy is manual. For hands-off operation you want
merges to main to deploy automatically.

**Add to `.github/workflows/ci.yml`** after the existing steps:

```yaml
  deploy:
    needs: lint-and-scan
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    steps:
      - uses: actions/checkout@v4
      - uses: superfly/flyctl-actions/setup-flyctl@master
      - name: Deploy to Fly.io
        run: fly deploy --remote-only
        env:
          FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}
```

**GitHub secret to add:** `FLY_API_TOKEN` — generate with `fly tokens create deploy`.

---

## P2 — Log persistence (open a new PR or manual setup)

**Why:** Fly.io VM logs are ephemeral — lost on machine restart. You need
persistent logs to debug production issues after the fact.

**Option A (recommended, free tier):** Logtail / Better Stack
- Create a free account at logs.betterstack.com
- `fly secrets set LOGTAIL_TOKEN=...`
- Add to `fly.toml`:
  ```toml
  [services.log_shipper]
    # Fly native log shipping — see https://fly.io/docs/reference/log-shipper/
  ```

**Option B:** Fly's built-in `fly logs` command streams live logs but doesn't
persist. Acceptable for active monitoring; not for retrospective debugging.

---

## P2 — CVE monitoring (open a new PR)

**Why:** `pip-audit --strict || true` in CI currently never blocks a deploy,
even for critical CVEs. Add a weekly scheduled scan that fails loudly.

**Add to `.github/workflows/ci.yml`:**

```yaml
on:
  schedule:
    - cron: '0 9 * * 1'   # every Monday 09:00 UTC
  # keep existing push/PR triggers
```

**Also:** Remove the `|| true` from the pip-audit step so it blocks CI on
strict vulnerabilities. If a known advisory is acceptable, use
`pip-audit --ignore-vuln PYSEC-...` with a comment explaining why.

---

## P3 — Notion data backup (open a new PR)

**Why:** All waitlist signups are stored only in Notion. If the integration
token expires, is revoked, or the database is accidentally deleted, all data
is gone with no recovery.

**Suggested implementation:**
- Write `scripts/export_waitlist.py` that queries the Notion API and writes
  a timestamped CSV to a local `exports/` directory (gitignored)
- Schedule a monthly manual export, or automate via a Fly cron job
- Alternative: add a `GET /admin/export-csv` endpoint gated behind a secret
  header (set as a Fly secret) that streams a CSV download

---

## P3 — 3D hero merge checklist

The `feature/3d-hero` branch adds a Three.js device animation to the hero.
Before merging into main after PR #1:

- [ ] Export `device.glb` from Blender (File → Export → glTF 2.0 → Binary)
- [ ] Drop `device.glb` into `app/static/` — no code changes needed
- [ ] Add `https://cdn.jsdelivr.net` to `_CSP_SCRIPT_SRC` in `app/main.py`:
      ```python
      _CSP_SCRIPT_SRC = (
          "'self' "
          "https://cdn.tailwindcss.com "
          "https://cdn.jsdelivr.net "
          "https://challenges.cloudflare.com"
      )
      ```
      Without this, the Three.js CDN import will be blocked by the CSP.
- [ ] Test locally with `APP_ENV=production` to verify CSP doesn't break the canvas
- [ ] Check that `feature/3d-hero` is rebased onto `main` post-merge of PR #1

---

## Deferred / nice-to-have

- **Tailwind build step** — Replace Tailwind CDN with a local build so
  `unsafe-inline` can be removed from `style-src`. Requires adding Node.js
  to the Docker build. Low urgency until traffic justifies it.
- **Rate limit GET /** — Currently only `POST /api/waitlist` is rate limited.
  Homepage is unprotected. Add `@limiter.limit("60/minute")` to the index
  route if scraping becomes a concern.
- **`elapsed_ms` threshold** — Currently 1500ms. Consider raising to 3000ms
  to reduce false positives from screen-reader or keyboard-only users on slow
  connections.
- **Smoke test after deploy** — Add a post-deploy step that curls `/healthz`
  and the homepage and fails the workflow if either returns non-200.
