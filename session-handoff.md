# Session Handoff Notes

## What I was asked
"Login to my session" → eventually clarified as: **I want to use my phone to view/control the Claude Code session running on my local Linux desktop** (titled "Recover from reboot and reconnect to cell phone", working in `~/automation`).

## What this session is
- A **separate** Claude Code on the Web cloud container
- Repo: `mattodunlap/sierra-fub-sync`
- Branch: `claude/session-login-oTxVV`
- Working tree clean, latest commit: `f7bb806 Create push_tags.yml`
- Not the local Linux session — different machine, different repo, no bridge between them

## Key finding
The Claude mobile app and claude.ai in a phone browser **only connect to Claude Code on the Web** (cloud containers). There is no feature to attach the mobile app to a Claude Code process running on your own Linux desktop.

So if you've been "accessing your Linux session from your phone all week," one of these is true:
1. **You've actually been starting new cloud sessions** from claude.ai/code on your phone each time — they look like Claude Code but are not your desktop session.
2. **You're using a separate remote-access app** on your phone (SSH client, VNC, Chrome Remote Desktop, Tailscale SSH, etc.) and just need to reopen that app.

## To actually reach the local Linux session from a phone
You need one of these on the phone:
- **SSH client**: Termius, Blink Shell (iOS), Termux, Prompt 3
- **Remote desktop**: Chrome Remote Desktop, RealVNC, AnyDesk
- **Tailscale + SSH** for secure access without port forwarding

Then on the Linux box, run Claude Code inside `tmux` so it survives disconnects:
```bash
tmux new -s claude
claude
# detach with Ctrl+b then d
# reattach later: tmux attach -t claude
```

⚠️ tmux/screen sessions **do not survive reboots** — after a reboot you have to start a new `claude` inside a fresh tmux.

## What I observed in the screenshot of the local session
- Title: "Recover from reboot and reconnect to cell phone"
- Working dir: `~/automation`
- Auto mode: ON
- Last actions: checked `systemctl --user list-unit-files` for `adrianne|tier`, read `~/automation/systemd_units/fub-texts-adrianne.s…`
- Currently running: `timeout 300 git -c core.compression=9 push origin main 2>&1 | tail -25`
- Status: Propagating ~4m 4s, push at 1m 45s of 5m cap, 4.2k tokens down
- It looked healthy, just a slow push. Ctrl+b to background, esc to interrupt.

## Open question to resolve
**What app on the phone has actually been being used to view that desktop session?** Until that's identified, reconnecting it isn't troubleshootable from this side.
