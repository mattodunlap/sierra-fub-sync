# System Map — Sierra ↔ FUB ↔ Corpus

The lead/marketing stack spans six platforms that were built incrementally and
never documented together. This is the map. Legend: ✅ verified from code I can
read · ❓ exists but contents not yet inspected · ⛔ cannot see from here.

## Components

| # | Component | Role | Visibility |
|---|-----------|------|-----------|
| 1 | **Sierra Interactive** (CRM) | Source of leads. Holds **lead status** (New/Qualify/Active/Prime/Pending/Closed/Junk/DoNotContact/…). Holds **Smart Lists "Claude 1–14"** and **Action Plans** that actually **send texts/emails** (Action Plan #1 = New-status only). | ⛔ UI only; API has **no** endpoint for lists/sends/status-writes |
| 2 | **Follow Up Boss** (CRM) | Contacts, custom fields (Sierra login URLs), tags, drip templates ("New Drip Campaign Email 1", etc.). Has a native Sierra integration. | ✅ via API |
| 3 | **GitHub repo** `sierra-fub-sync` | Scheduled jobs + webhook (below). | ✅ full |
| 4 | **Corpus pipeline** (on droplet, backed up to Drive) | RAG/enrichment over FUB conversation text. | ❓ filenames seen, code read **blocked pending Drive approval** |
| 5 | **Droplet `maittrix`** (DigitalOcean, Tailscale `100.96.93.82`) | Runs Claude (tmux/systemd) + corpus services + creds-push. | ⛔ currently **down/unreachable** |
| 6 | **Fly.io** | Unknown service (suspected lead/CRM automation). | ⛔ not in this repo |
| 7 | **Render** | Hosts `webhook_handler.py`. | ✅ code |
| 8 | **GitHub Actions** | Cron scheduler for the two jobs below. | ✅ |
| 9 | **Google Drive** | Backup of corpus code + logs. | ❓ list only |
| 10 | **Tailscale** | Private network linking phone/laptops/droplet. | ✅ |

## Data flows (what writes where)

```
                    ┌───────────────────────────── Sierra (status, Smart Lists, Action Plans → SENDS)
                    │  ▲ writes status? ──┐
   reads leads/tags │  │                 │ (UNVERIFIED write-paths — the bug surface)
                    ▼  │                  │
GitHub Actions ─────┤  │                  ├── website re-registration → status=New
  • sync.yml  (5m)  │  │                  ├── Sierra API POST/PUT /leads  → ❓ corpus? ⛔ Fly?
      Sierra leads ─┼──┼──► FUB login-URL │ │                                 (repo: ✅ NONE)
  • push_tags.yml(1h)  │      custom field│ ├── FUB→Sierra native integration (tags/contacts back?)
      Sierra tags ─────┼──► FUB tags       │ └── auto-login link click → activity → Sierra
        (SPRIORITY,    │   (SPRIORITY,     │       "active" automation → status flips
         2026 Daily…)  │    2026 Daily…)   │
                       │                   │
webhook_handler.py ────┘                   │
  (Render/Fly): Sierra new-lead webhook → create/update FUB contact (NEVER writes Sierra)

Corpus pipeline (droplet):
  pull_fub_text_corpus.py ─reads─► FUB texts ─► corpus_db / corpus_rag
  corpus_enricher.py (timer) ─► enrich      scrape_corpus_external.py ─► external ❓(writes Sierra??)
  corpus-github-sync (timer) ─► back up to GitHub/Drive    corpus-monitor.service
```

## The bug surface (wrong people get the "New-only" Action Plan)

For a past client / junk lead to receive Action Plan #1 (New-only), their **Sierra
status must read "New"** (or they were enrolled while New and never unenrolled).
The ONLY things that can set Sierra status to New:

1. **Website re-registration** — a form fill / the auto-login link re-registering them.
2. **A Sierra API `POST`/`PUT /leads`** — **this repo does NONE** (✅ verified). Open
   questions: the **corpus `scrape_corpus_external.py`** (❓) and the **Fly service** (⛔).
3. **FUB → Sierra integration** pushing contacts/tags back into Sierra.
4. **A Sierra automation** like "site activity → set Active/New" — and the auto-login
   links this project sends can generate that activity (even via email link-scanners).

## What's needed to close the unknowns
- ✅ Ruled out: the GitHub repo's jobs/webhook (they only write to FUB).
- ❓ **Read the corpus scripts** — need Google Drive read approval. Target:
  `scrape_corpus_external.py`, `corpus_enricher.py` (do they write to Sierra?).
- ⛔ **Locate the Fly service** — what it is, what it writes. (Add its repo if it has one.)
- ⛔ **One Sierra lead's status history** — confirms whether status is being flipped vs. enrollment never stopping.
