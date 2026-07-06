# Maittrix Command Center — demo portal

A self-contained, static demo of the Maittrix operator portal. Everything —
login, dashboard, charts, demo data — lives in a single `index.html` with no
build step and no backend, so it can be hosted anywhere that serves static
files.

## Demo login

| Field | Value |
|---|---|
| Email | `demo@gmail.com` |
| Access code | `1234` |

The gate is client-side and for demo flow only — it is **not** security. Don't
put anything private behind it.

## What's inside

- **Overview** — hero "resolved by AI" number, KPI tiles with sparklines, a
  14/30/7-day lead-activity chart (crosshair + tooltip + table view), lead-flow
  funnel, operator log with expandable AI reasoning, "Needs you" priority
  queue, speed-to-lead SLA card.
- **Live inbox** — featured conversation thread with AI reasoning and
  extracted criteria, live message list.
- **Nurture** — warming-up hero, buying-signal and in-conversation lists.
- **Analytics** — reply rate / lead volume by source, message-volume trend,
  AI insights. Every chart has a table toggle.
- **Sync health** — the Sierra ↔ Follow Up Boss pipeline this repo actually
  runs: leads matched, auto-login URLs written, tag pushes, worker health,
  live-tail log. Numbers mirror real runs from this repo's sync scripts.
- **Settings** — brand, AI voice & autonomy, integrations, team.

Light + dark theme (auto from OS, manual toggle in the sidebar), fully
responsive with a bottom tab bar on phones.

All lead names, conversations, and metrics are fictional sample data defined
at the top of the script section in `index.html` — edit them there to re-theme
the demo for a different team or market.

## Run locally

```bash
cd portal
python3 -m http.server 8080
# open http://localhost:8080
```

## Deploy

Any static host works (Render static site, Netlify, Vercel, Fly, GitHub
Pages). `render.yaml` in the repo root already defines a `maittrix-portal`
static site pointing at this directory.
