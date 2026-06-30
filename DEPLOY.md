# Deployment Guide

Two pieces to deploy:

1. **GitHub Actions polling sync** — the catch-everything backstop, runs every 30 min
2. **Render webhook** — real-time updates for new lead registrations

Both pieces share the same GitHub repo. Set up the repo first.

## 1. Push to a private GitHub repo

If you don't have a GitHub account yet, sign up at https://github.com (free).

```bash
# In your project folder, open Command Prompt and run:
cd "C:\Users\matto\OneDrive\Documents\Claude\Projects\Auto Login Link From Sierra To FUB"
git init
git add .
git commit -m "Initial commit"
```

Then on github.com:

1. Click the **+** in the top right → **New repository**
2. Name it: `sierra-fub-sync`
3. Set it to **Private** (very important — your `.env` is gitignored, but private adds defense in depth)
4. Don't add a README, .gitignore, or license (we already have one)
5. Click **Create repository**
6. On the next page, GitHub shows you commands. Use the **"…or push an existing repository from the command line"** block:

```bash
git remote add origin https://github.com/YOUR_USERNAME/sierra-fub-sync.git
git branch -M main
git push -u origin main
```

If git asks for credentials, use a personal access token (Settings → Developer Settings → Personal Access Tokens → Tokens (classic) → Generate new token, give it `repo` scope).

## 2. Configure GitHub Actions secrets (for polling)

In your new repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**.

Add these four:

| Name | Value |
|---|---|
| `SIERRA_API_KEY` | (your Sierra key) |
| `FUB_API_KEY` | (your FUB key) |
| `FUB_CUSTOM_FIELD` | `customSierraLoginURL` |
| `SIERRA_ORIGINATING_SYSTEM` | `FUB-AutoLogin-Sync` |

The workflow will run automatically every 30 min. To run it once manually right now: **Actions** tab → **Sierra-FUB Sync** → **Run workflow**.

## 3. Deploy webhook to Render

1. Go to https://render.com and sign up (free tier, no card required)
2. Click **New +** → **Web Service**
3. Click **Connect a repository** → authorize GitHub access → pick `sierra-fub-sync`
4. Render auto-detects the `render.yaml`. Confirm the settings:
   - **Name:** `sierra-fub-webhook` (or whatever)
   - **Region:** pick closest to you (Ohio = Ohio region)
   - **Branch:** `main`
   - **Plan:** Free
5. Under **Environment Variables**, fill in the secret values you marked `sync: false`:
   - `SIERRA_API_KEY` = your Sierra key
   - `FUB_API_KEY` = your FUB key
   - `WEBHOOK_SECRET` = any random string (e.g., a UUID — generate at https://www.uuidgenerator.net)
6. Click **Create Web Service**
7. Wait ~3 minutes for first deploy
8. Once "Live," copy the URL Render assigned (something like `https://sierra-fub-webhook.onrender.com`)
9. Test it: open `https://YOUR-RENDER-URL/` in a browser. Should show `{"status":"ok"}`. That confirms the service is up.

## 4. Configure Sierra to send webhooks

1. Sierra Admin → **Integrations** → look for **Webhooks** (might be under Direct API)
2. Add a new webhook:
   - **Event:** "New Lead Registration" (or equivalent — pick the event for new lead creation)
   - **URL:** `https://YOUR-RENDER-URL/sierra-webhook`
   - **Custom Header:** key=`X-Webhook-Secret`, value=(the same `WEBHOOK_SECRET` you set in Render)
3. Save
4. To test: register a fake lead on your IDX site (use a private/incognito browser, fake name, real-looking email you control). Within seconds, the FUB contact should be created with the auto-login URL already populated.

If Sierra doesn't show a webhooks UI, email support@sierrainteractive.com:
> "How do I configure outbound webhooks for new lead registrations? I want to send a POST request to my own endpoint when a new lead registers, including the lead ID in the payload."

## 5. Verify the whole stack

After deploying, verify:

- [ ] `run_full_backfill.bat` finished successfully (existing leads have URLs in FUB)
- [ ] GitHub Actions ran a successful sync (Actions tab shows green)
- [ ] Render service shows "Live" and `/` returns OK
- [ ] Sierra webhook test fires correctly (check Render logs for incoming requests)
- [ ] FUB email template merge tag resolves to the correct URL when sent

## Accessing Claude Code on the droplet (from phone or computer)

The droplet runs an always-on Claude Code session inside `tmux` so you can attach
to it from any device on your Tailscale network (phone, laptop) and have it
survive disconnects, crashes, and reboots.

### Network

The droplet is reachable at its Tailscale address `100.96.93.82`. Every device
that connects must have Tailscale installed and signed into the **same** account,
with the VPN toggled **on**. This keeps the droplet off the public internet — no
port forwarding required.

### Permanent, self-restarting session (one-time setup on the droplet)

Confirm the binary paths first:

```bash
which tmux && which claude
```

Create a systemd service that keeps a `tmux` session named `claude` alive:

```bash
cat > /etc/systemd/system/claude-session.service <<'EOF'
[Unit]
Description=Persistent self-restarting Claude Code session in tmux
After=network-online.target
Wants=network-online.target

[Service]
Type=forking
User=root
WorkingDirectory=/root
# login shell (-l) loads PATH so `claude` resolves; while-loop relaunches it if it ever exits
ExecStart=/bin/bash -lc "tmux new-session -d -s claude 'while true; do claude; sleep 2; done'"
ExecStop=/bin/bash -lc "tmux kill-session -t claude"
RemainAfterExit=yes
KillMode=none

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now claude-session.service
```

Verify:

```bash
systemctl status claude-session.service   # should say "active"
tmux ls                                    # should list: claude
```

This survives reboots (systemd relaunches on boot), self-restarts Claude if it
exits (the `while true` loop), and always leaves a `claude` tmux session waiting
to attach. It relies on the droplet's Claude OAuth credentials staying fresh —
that is what the `claude-creds-push` timer is for.

### Connecting from any device

```bash
ssh root@100.96.93.82
tmux attach -t claude          # or: tmux attach -t claude || tmux new -s claude
```

To detach without stopping Claude: press `Ctrl-b` then `d` (or just close the
window). On iOS SSH clients (Termius, Blink, etc.), save `root@100.96.93.82` as a
host and set its "command on connect" to
`tmux attach -t claude || tmux new -s claude` for one-tap access.

### Persistent session logging

To keep a running log of the session output, enable `tmux` pane logging. It pipes
everything the session prints to a file, and a tmux hook re-enables it
automatically whenever the session is recreated (e.g. after a reboot):

```bash
mkdir -p /root/claude-logs

# Start logging the session running right now
tmux pipe-pane -t claude -o 'cat >> /root/claude-logs/claude.log'

# Auto-log every future session on boot/restart
cat >> /root/.tmux.conf <<'EOF'
# auto-log every pane to /root/claude-logs/<session>.log
set-hook -g session-created 'pipe-pane -o "cat >> /root/claude-logs/#{session_name}.log"'
set-hook -g pane-focus-in   'pipe-pane -o "cat >> /root/claude-logs/#{session_name}.log"'
EOF
```

Read or follow the log from any device:

```bash
tail -f /root/claude-logs/claude.log      # live tail
less /root/claude-logs/claude.log         # scroll full history
```

Note: this captures raw terminal output, so the file includes TUI redraw/escape
codes and reads noisily. For a clean conversation transcript, use Claude Code's
own structured session history under `~/.claude/` (per-project `.jsonl` files)
instead.

## Troubleshooting

**Render service shows "Application failed to respond"**: usually a missing env var. Check the Render logs tab.

**Webhook returns 401**: the `X-Webhook-Secret` header from Sierra doesn't match `WEBHOOK_SECRET` in Render env vars. Fix by aligning them.

**Render free tier cold starts**: after 15 min of no traffic, the service spins down. First webhook hit takes ~30 sec to wake up. Subsequent hits are instant. Polling sync (every 30 min) will keep it warm if you also deploy a small "cron-ping" service, but for new-lead webhooks the cold start is acceptable.
