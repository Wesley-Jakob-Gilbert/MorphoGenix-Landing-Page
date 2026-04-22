# Deploying MorphoGenix to Fly.io

One-time setup (Windows PowerShell).

## 1. Install flyctl

```powershell
iwr https://fly.io/install.ps1 -useb | iex
```

Then restart your terminal and verify:

```powershell
fly version
```

## 2. Sign in

```powershell
fly auth login
```

This opens a browser. First time, you'll also need to add a credit card — Fly no longer has a free tier for new orgs, but the smallest always-on VM runs about $2–4/month.

## 3. Create the app (first time only)

From the repo root:

```powershell
fly launch --no-deploy --copy-config --name morphogenix-web
```

`--copy-config` keeps the `fly.toml` that's already in the repo. Answer **No** to databases and Redis. Pick `den` (Denver) as the region if asked.

## 4. Set secrets

```powershell
fly secrets set `
  NOTION_TOKEN=secret_your_integration_token `
  NOTION_DATABASE_ID=2fdab5cfd494473aa2d41d04e09ef6c0
```

(The backtick is the PowerShell line continuation.)

Verify:

```powershell
fly secrets list
```

## 5. Deploy

```powershell
fly deploy
```

First deploy takes 2–4 minutes (image build + push). Subsequent deploys are faster because Docker layers cache.

When it finishes, open:

```powershell
fly open
```

You'll land at `https://morphogenix-web.fly.dev`.

## 6. Logs and health

```powershell
fly logs              # live tail
fly status            # machines + health
fly ssh console       # shell into the container
```

The app exposes `/healthz` which returns `{"ok": true}` — Fly hits this every 30s per `fly.toml`.

## 7. Custom domain (when you have one)

At Fly:

```powershell
fly certs create morphogenix.com
fly certs create www.morphogenix.com
```

Fly will print exact DNS records. At GoDaddy's DNS panel for `morphogenix.com`:

- **Apex (`@`)**: add the A record (IPv4) and AAAA record (IPv6) Fly gave you.
- **`www`**: add a CNAME pointing to `morphogenix-web.fly.dev`.

Then check status until both say `Issued`:

```powershell
fly certs show morphogenix.com
fly certs show www.morphogenix.com
```

Propagation is usually 2–15 minutes with GoDaddy.

## Cost sanity check

Current config runs one `shared-cpu-1x` / 256MB VM 24/7 in Denver. At published rates that's about **$2–3/month** before bandwidth. Bandwidth for a landing page with a waitlist form is effectively zero. See [Fly.io Pricing](https://fly.io/docs/about/pricing/).

## Scaling down / pausing

If you ever want to pause the app (stop billing):

```powershell
fly scale count 0
```

Resume with:

```powershell
fly scale count 1
```

## Useful one-liners

```powershell
fly deploy --remote-only        # build on Fly's builders (no local Docker needed)
fly restart                     # kick the machine
fly apps destroy morphogenix-web  # nuke everything
```
