# Deploying MT-RFP for your team (free, no VPS)

This runs the whole app on **one machine you keep on** (your PC) and exposes it
to your reps through a **free tunnel** that gives a public **HTTPS** URL — no
cloud bill, no port-forwarding, no domain to buy. Your NVIDIA key stays on your
machine, the 6-hour sync scheduler and local file storage just work, and HTTPS
means the phone voice feature works.

In this mode the backend serves the built frontend, so the **whole app is one
origin on port 8000** and a single tunnel URL covers everything.

---

## 1. Configure

Copy `.env.example` to `.env` and set at least:

```
NEMOTRON_API_KEY=nvapi-...        # your NVIDIA key (rotate the one shared in chat)
MTRFP_TEAM_PASSWORD=some-strong-shared-password
# optional but recommended:
USAC_APP_TOKEN=...                # free, avoids throttling
```

`MTRFP_TEAM_PASSWORD` is what your reps type to sign in. **It is required
before you expose the app** — without it the API is open and anyone with the
URL could spend your NVIDIA credits.

## 2. Build the frontend and start the server

With `make`:

```
make serve
```

Without `make` (Windows PowerShell):

```powershell
cd frontend; npm install; npm run build
cd ..\backend; python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open http://localhost:8000 — you should see the **team login**. Sign in with
your password to confirm it works. Keep the server bound to `127.0.0.1` (the
tunnel connects to it locally); don't bind `0.0.0.0` unless you mean to expose
it on your LAN.

## 3. Expose it with a free tunnel

### Option A — Tailscale Funnel (recommended: stable HTTPS URL, no domain)

1. Install Tailscale: https://tailscale.com/download , then sign in:
   ```
   tailscale up
   ```
2. Publish port 8000 to the public internet over HTTPS:
   ```
   tailscale funnel 8000
   ```
   (add `--bg` to keep it running in the background).
3. It prints a stable URL like `https://your-machine.your-tailnet.ts.net`.
   Share that URL **and the team password** with your reps.

Free on Tailscale's Personal plan, and the URL stays the same across restarts.

### Option B — Cloudflare quick tunnel (zero account, URL changes each run)

```
cloudflared tunnel --url http://localhost:8000
```

Prints a `https://<random>.trycloudflare.com` URL. Great for a quick test, but
the URL changes every time you restart it. For a permanent Cloudflare URL you'd
need a named tunnel + a domain on Cloudflare (a domain is ~$10/yr — only if you
want a branded URL).

## 4. Keep it running

- The host machine must stay awake — use the in-app **Keep awake** toggle
  (top bar), and set the machine's power settings to never sleep.
- To run the server unattended on Windows, run it as a background task (Task
  Scheduler "At log on", or a tool like NSSM to install it as a service) so it
  survives reboots. On macOS/Linux use `launchd`/`systemd` or `tmux`.

## Updating

```
git pull
make serve        # rebuilds the frontend and restarts the server
```

## Security notes

- The team password gates every API call; sessions expire after 7 days
  (`MTRFP_SESSION_TTL`).
- Rotate your NVIDIA key if it was ever shared, and put the new value in `.env`.
- Everything stays local except calls to USAC (read-only) and the NVIDIA API.
- Only share the tunnel URL + password with people you want using your key.
