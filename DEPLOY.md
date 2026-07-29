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
# optional but recommended:
USAC_APP_TOKEN=...                # free, avoids throttling
```

Then create a sign-in user for each rep (name + 4-digit PIN):

```
cd backend
python -m app.manage_users add kim "Kim" 6969
python -m app.manage_users add rob "Rob" 1234
python -m app.manage_users list
```

Credentials are stored **hashed** in `data/users.json` (gitignored). **At
least one user is required before you expose the app** — with no users the API
is open and anyone with the URL could spend your NVIDIA credits. Reps sign in
with their name and PIN, and Matt (the assistant) greets them by name.

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

## Always-on hosting — Oracle Cloud Always Free ($0/month, recommended)

Hosting on a laptop means the site dies whenever the laptop is off. Oracle's
Always Free tier gives a real, permanently-free VM with persistent disk — the
app runs 24/7 and your laptop becomes just another way to access it.

**One-time setup (~20 minutes, most of it Oracle's signup):**

1. **Create the account** at signup.oraclecloud.com. It asks for a credit
   card for identity verification — Always Free resources never charge it.
   Pick a home region near you (e.g. US-Ashburn / US-Phoenix).
2. **Create the VM**: Compute → Instances → Create.
   - Image: **Ubuntu 24.04**
   - Shape: **VM.Standard.E2.1.Micro** (marked "Always Free-eligible").
     (Ampere A1 is also free and beefier, but often shows "out of capacity" —
     the Micro always works and is plenty for this app.)
   - Download the **private key** it offers (`.key` / `.pem`) — that's your
     SSH login. Note the VM's **public IP** once it's running.
   - No networking changes needed: the app publishes itself via Tailscale
     Funnel (outbound-only), so Oracle's default block-all-inbound firewall
     can stay as-is.
3. **On this laptop** — bundle the data (DB, drafts, statuses, price list,
   `.env`) and upload it:

   ```powershell
   .\scripts\make-data-bundle.ps1
   scp -i <path-to-key.pem> "$HOME\Desktop\rfp-rockstar-bundle.zip" ubuntu@<VM-IP>:~/
   ```

4. **On the VM** (`ssh -i <key.pem> ubuntu@<VM-IP>`):

   ```bash
   curl -fsSL https://raw.githubusercontent.com/robsalsman/MT-RFP/main/scripts/deploy-oracle.sh | bash
   ```

   Midway it prints a **Tailscale login link** — open it in your browser and
   approve the machine (same Tailscale account as before). If Funnel needs
   enabling for the new node, the command prints that link too. The script
   ends by printing the **permanent public URL** — share that with the team.

5. **Optional cleanup on the laptop**: `tailscale funnel --https=443 off`
   (retires the old laptop URL) and disable the "RFP Rockstar" scheduled
   task if you don't want a local copy running.

The VM auto-starts the app on boot (systemd) and Funnel persists, so
reboots, patches, and power cuts all self-heal.

## Updating

Laptop-hosted:

```
git pull
make serve        # rebuilds the frontend and restarts the server
```

Cloud-hosted (on the VM): re-run the deploy script — it pulls the latest
code and restarts the service. The UI build (`frontend/dist`) ships in the
data bundle, so after UI changes: rebuild locally, re-run
`make-data-bundle.ps1`, `scp` it up, and re-run the deploy script.

## Security notes

- The team password gates every API call; sessions expire after 7 days
  (`MTRFP_SESSION_TTL`).
- Rotate your NVIDIA key if it was ever shared, and put the new value in `.env`.
- Everything stays local except calls to USAC (read-only) and the NVIDIA API.
- Only share the tunnel URL + password with people you want using your key.
