# CLAUDE.md — Project Context for Sierra ↔ FUB Sync

**Read this first.** Claude Code auto-loads this file at session start. It encodes everything previous sessions discovered the hard way so you don't repeat the discovery work.

The user is **Matthew Dunlap** (matthew@teamdunlaprealty.com), team leader of a Las Vegas real estate team. Repo: `mattodunlap/sierra-fub-sync`.

---

## 1. What this project is

A bridge between two CRMs:

- **Sierra Interactive** — the IDX/lead-generation system. Source of truth for leads.
- **Follow Up Boss (FUB)** — the working CRM where the team manages contacts, sends emails/SMS, runs action plans.

Sierra and FUB have a *native* integration that syncs contacts but **does not sync tags or the per-lead Sierra "auto-login URL"**. This repo fills both gaps via:

1. **Auto-login URL sync** (`sierra_fub_sync.py`) — pulls each Sierra lead's auto-login URL into a FUB custom field so it can be merged into email/SMS templates. Lets recipients click a link in a marketing email and land in their Sierra portal already logged in.
2. **Tag push** (`push_tags_batch.py`) — for each tag listed in `tags_to_push.txt`, finds Sierra leads with that tag and adds the same tag to the matching FUB contact (matched by email).
3. **Webhook receiver** (`webhook_handler.py`) — FastAPI app on Render. Sierra POSTs to it whenever a new lead registers; the handler immediately populates the auto-login URL on the FUB contact (creating it if needed).

Two GitHub Actions workflows run on cron:
- `sync.yml` — every 5 min, runs `python sierra_fub_sync.py --recent --recent-pages=2` (URL backfill, incremental).
- `push_tags.yml` — every hour on the hour, runs `python push_tags_batch.py --write`.

Production webhook lives at `https://sierra-fub-sync.onrender.com/sierra-webhook` (Render free tier — cold-starts after 15 min idle, first call ~30s).

---

## 2. Hard-won facts about the Sierra API

Base URL: `https://api.sierrainteractivedev.com`
Auth header: `Sierra-ApiKey: <key>` (plus `Sierra-OriginatingSystemName: FUB-AutoLogin-Sync`).

### 2.1 Finding a lead — the #1 pain point

If a new session "can't find a lead in Sierra," it is almost always one of these:

**(a) Wrong pagination parameter name.** Sierra's `/leads/find` endpoint expects `pageNumber`, NOT `page`. Using `page` is silently ignored and **always returns page 1**. This bit several earlier sessions — `check_pagination.py` was written to prove it. If you write new Sierra code, **always use `pageNumber`**.

**(b) Searching by email/phone.** The right call is:
```python
GET /leads/find?email=<email>&pageNumber=1&pageSize=5
# or
GET /leads/find?phone=<10-digit-string>&pageNumber=1&pageSize=5
```
Sierra returns up to `pageSize` candidates; **filter the results client-side** by exact email-lowercase match, because Sierra's `email=` is a fuzzy/contains search. See `test_one_lead.py:find_sierra_lead_by_email` and `match_tagged_contacts.py:find_sierra_by_email` for the canonical pattern.

**(c) Phone normalization.** Strip all non-digits, take the **last 10** characters. See `match_tagged_contacts.py:normalize_phone`. Sierra phone fields can be `phone`, `phoneNumber`, `mobilePhone`, or `homePhone` — check all of them.

**(d) Pulling the whole lead detail.** Use `GET /leads/get/{lead_id}` — note `/get/` is a literal path segment, not a verb. Returns `{"success": true, "data": {...lead...}}`. The response wrapper sometimes has `data.lead`, sometimes `data` is the lead directly — handle both (see `webhook_handler.py:get_sierra_lead`).

### 2.2 Fields on a Sierra lead

From `/leads/get/{id}`, the top-level keys on a lead detail are:
```
id, firstName, lastName, leadStatus, listingAgentStatus, lenderStatus,
email, emailStatus, phone, phoneStatus, leadType, assignedTo, listingAgent,
lender, searchPreference, creationDate, updateDate, source,
marketingEmailOptOut, textOptOut, eAlertOptOut, partnerLink,
streetAddress, city, state, zip, shortSummary, pondId, visits
```

**Notable:**
- `assignedTo` is an object with `agentUserFirstName`, `agentUserLastName`, etc.
- `email` may be `null` or a placeholder like `notvalidemail@...` — skip those.
- **There is NO `tags` field on the lead detail.** Tags are not returned on lead objects. To find tagged leads you must filter the listing (see 2.3).

### 2.3 Tags in Sierra — the trap

This was a multi-session investigation. The conclusions, all proven empirically (see `sierra_tags_probe.txt`, `priority_gap_investigation.txt`):

- **No `/tags`, `/leads/{id}/tags`, or similar endpoint exists.** Sierra returns 404 for every obvious variant.
- **Two endpoints that DO work:**
  - `GET /leadTags?pageNumber=N&pageSize=100` — lists all tag *definitions* (id, name). There are 687 of them.
  - `GET /leadTags/{leadId}?pageNumber=N&pageSize=100` — lists tag definitions associated with a single lead (paginates, can return all 687 not just that lead's — verify before trusting).
- **To get leads with a specific tag**, use the listing filter:
  ```
  GET /leads/find?tags=<TAG_NAME>&pageNumber=N&pageSize=100
  ```
  ⚠️ The filter parameter MUST be `tags` (plural). Singular `tag`, `tagName`, `leadTag`, `category` are **silently ignored and return ALL leads** (the API returns 200 with `totalRecords=10388` instead of erroring). Verified in `sierra_tags_probe.txt` step 5.
- **Tag filter is case-INsensitive** (e.g. `SPRIORITY`, `Spriority`, `spriority`, `sPriority` all return the same 98 leads) but **whitespace-sensitive** (`" SPRIORITY"` with leading space returns 0; trailing space is tolerated). And **`-`, `_` are NOT equivalent to a space** — `S-Priority` ≠ `S Priority`.
- **Duplicate tag definitions exist** with the same effective meaning but different IDs/spellings. Real example from this account:
  ```
  id=551122  name='S Priority'   -> 1 lead (essentially abandoned)
  id=551117  name='SPRIORITY'    -> 98 leads (the active one)
  ```
  When the user references "the S Priority tag," they almost certainly mean `SPRIORITY` (98 leads). When in doubt, ask.
- **Sierra UI count vs API count can disagree.** Sierra UI showed 116 SPRIORITY but API returned 98 — could be UI merging similar tags, an indexing lag, or filter quirks. `investigate_priority_gap.py` was the diagnostic.

### 2.4 Pagination shape

Every Sierra list response is:
```json
{"success": true, "data": {
    "totalRecords": N, "totalPages": N, "pageNumber": 1, "pageSize": 100,
    "leads": [...] | "records": [...]
}}
```
Loop pages until `pageNumber >= totalPages` OR an empty array. **Important behavioral quirk:** pagination is **ascending by lead ID**, so the newest leads live on the LAST page. That's why `sync_recent()` in `sierra_fub_sync.py` checks the last 2 pages, not the first.

---

## 3. Hard-won facts about the FUB API

Base URL: `https://api.followupboss.com/v1`
Auth: HTTP Basic with the API key as the username and an empty password — `auth=(FUB_API_KEY, "")`.

### 3.1 Rate limits

**1000 requests per 10 minutes per API key.** This is tight. Every write should sleep `SLEEP_BETWEEN_WRITES = 0.7` seconds. On 429, FUB returns a `Retry-After` header (seconds). The canonical retry helper is `sierra_fub_sync.py:_fub_request_with_retry` — use it.

### 3.2 Finding a person

```python
GET /people?email=<email>&fields=allFields
```
**Always include `fields=allFields`** — without it, custom field values are NOT returned, which makes the "already set" comparison wrong and causes unnecessary writes.

Email lookup returns at most one match. Returns `{"people": [...]}`.

### 3.3 Pagination

FUB uses `_metadata.nextLink` (sometimes `metadata.next`) — follow the absolute URL. Don't try to compute the next URL yourself. Pattern:
```python
next_url = f"{FUB_BASE}/people?limit=100&fields=allFields"
while next_url:
    r = requests.get(next_url, auth=(FUB_API_KEY, ""), timeout=30)
    ...
    meta = r.json().get("_metadata", {}) or r.json().get("metadata", {})
    next_url = meta.get("nextLink") or meta.get("next")
```

### 3.4 Updating a person — preserving tags

`PUT /people/{id}` with a JSON body of just the fields you want to change. **Tags are an array — sending `{"tags": [...]}` REPLACES the array**, it does not append. To add a tag, fetch existing tags, append, then PUT the full new list. Canonical: `push_priority_tag.py:add_tag_to_fub`.

### 3.5 Updating templates — the read-only field trap

`PUT /templates/{id}` and `PUT /textMessageTemplates/{id}` reject several fields. Before PUT, fetch the full template and **strip these keys**:
```
id, created, updated, createdById, updatedById,
isEditable, isShareable, isDeletable,
imported, isMobile, actionPlans, automations,     # email only
totalSent, totalReplies, createdBy, sentPeopleCount,
effectivenessScore, windowedSent, windowedReplies,
windowedOptOutRate, totalOptOutRate                # SMS only
```
Sanity-check that `name` is non-empty before PUT. Canonical: `replace_ylopo_to_sierra.py:update_template`.

### 3.6 Custom fields

Listed via `GET /v1/customFields`. The field used by this project:
```
name (API):  customSierraLoginURL
```
Stored as env var `FUB_CUSTOM_FIELD` (also exported in `render.yaml` and the workflow secrets). To read or write it, just use that string as a top-level key on the person object (in GETs with `fields=allFields`, or in PUT bodies).

### 3.7 Template endpoints — what exists

Confirmed working (`probe_fub_endpoints.py`):
- `templates` (response wrapper key: `templates`, body field: `body`) — email templates
- `textMessageTemplates` (response wrapper key: `textmessagetemplates`, body field: `message`) — SMS templates

Non-existent: `emailTemplates`, `smsTemplates`, `textTemplates`. Use only the two confirmed above.

---

## 4. The auto-login URL — how it's built

Format: `https://{subdomain}.thevegasagent.com/?userid={lead_id}&sentfrom=auto`

The subdomain is picked from the lead's assigned agent's lowercased first name:

| Agent first name | Subdomain |
|---|---|
| `matthew` (team leader) | `www` |
| `adrianne` | `adrianne` |
| anything else / unassigned | `www` (DEFAULT) |

Canonical: `sierra_fub_sync.py:build_login_url`. If new agents join the team, **add them to both `AGENT_SUBDOMAINS` dicts** — there are TWO copies, one in `sierra_fub_sync.py` and one in `webhook_handler.py`. Keep them in sync. (Yes, this is duplication; nobody has refactored it because each file needs to deploy independently.)

The URL is written to the FUB custom field `customSierraLoginURL`. FUB email templates reference it via the merge tag `%custom_sierra_login_url%`. SMS templates use the same merge tag — but for SMS you should run the URL through a branded link shortener first (Bitly w/ custom domain, Short.io) so it looks clean.

---

## 5. People in the data (handy reference)

| Who | Sierra lead ID | Email | Notes |
|---|---|---|---|
| Leilani Johnson | 2443063 | (test lead — known good) | Used in `test_webhook.py` for end-to-end webhook tests |
| Joan Nikolaus | 4988199 | jnikolaus36@gmail.com | Used in `probe_joan.py` — known-good SPRIORITY tag holder |
| Matthew Dunlap | — | matthew@teamdunlaprealty.com | The user. Team leader. |
| Adrianne Dunlap | — | — | Second agent on the team |

---

## 6. Project file map (what to read for what)

### Production code (deployed)
- `sierra_fub_sync.py` — polling sync. `--recent` mode is what the cron uses; default mode is a full backfill.
- `webhook_handler.py` — FastAPI app on Render.
- `push_tags_batch.py` — multi-tag push driven by `tags_to_push.txt`. Default DRY RUN; pass `--write`.
- `.github/workflows/sync.yml`, `.github/workflows/push_tags.yml` — the cron jobs.
- `render.yaml` — webhook deploy config.

### Single-task scripts
- `match_tagged_contacts.py "Tag Name" [--write] [--fallback-generic]` — for a FUB tag, walk all contacts, look each up in Sierra (email then phone), set the auto-login URL.
- `push_priority_tag.py "Tag Name" [--write]` — single-tag version of `push_tags_batch.py`.
- `replace_ylopo_to_sierra.py [--write]` — find/replace `%custom_ylopo_listing_alert%` → `%custom_sierra_login_url%` in all FUB email/SMS templates. Backs up every template to `template_backups/<timestamp>/` before writing.
- `find_fub_duplicates.py` — walks all FUB contacts, reports dupes by email and phone. Output: `fub_duplicates.txt`.
- `count_fub_populated.py` — counts how many FUB contacts have `customSierraLoginURL` set.
- `list_fub_templates.py` — lists email + SMS templates, flags ones with Ylopo merge tags or hardcoded Sierra links.

### Diagnostics / probes (one-shot research scripts, kept for repeatability)
- `test_connections.py` — pre-flight check. Verifies both API keys + custom field. Read-only, safe to re-run.
- `test_one_lead.py <email> [--write]` — full end-to-end test on one lead. Default DRY RUN.
- `test_webhook.py` — POSTs a test payload to the deployed Render webhook.
- `probe_sierra.py`, `probe_sierra_tags.py`, `probe_fub_endpoints.py`, `probe_fub_priority.py`, `probe_joan.py jnikolaus36@gmail.com` — Sierra/FUB endpoint discovery.
- `check_pagination.py` — proves the `page` vs `pageNumber` bug.
- `debug_page2.py` — proves the "already set" comparison logic on a real page.
- `investigate_priority_gap.py` — the SPRIORITY UI-count-vs-API-count investigation.
- `compare_tags.py`, `compare_priority_tag.py [tag]` — Sierra↔FUB tag comparison reports.
- `peek_template.py [template_id]` — dumps one FUB template's full body.

### Result artifacts (don't run, just read)
- `match_summary.txt` — last `match_tagged_contacts.py` run summary.
- `priority_push_summary.txt` — last `push_priority_tag.py` summary.
- `priority_tag_compare.txt` — last `compare_priority_tag.py` report (long; uses head/tail).
- `priority_gap_investigation.txt`, `fub_priority_probe.txt`, `sierra_tags_probe.txt`, `joan_probe.txt` — probe outputs, contain the empirical findings cited in sections 2 and 3.
- `unmatched_contacts.txt` — 1,844 FUB contacts that `match_tagged_contacts.py` couldn't find in Sierra. Mostly imported old contacts without Sierra presence.

### Backups
- `template_backups/<timestamp>/{email|sms}_<id>.json` — full pre-change snapshot of any template `replace_ylopo_to_sierra.py --write` touched. Three timestamps exist; the most recent is `20260507_133335`.

### Deployment glue
- `README.md` — user-facing overview.
- `DEPLOY.md` — step-by-step deploy guide (GitHub Actions secrets + Render setup).
- `archive/` — old `.bat` runners from before GitHub Actions took over. Kept for reference, not used in prod.
- `*.bat` files at repo root — Windows convenience launchers Matthew uses locally. Each calls one Python script with the right flags.

---

## 7. Environment variables

Required everywhere:
```
SIERRA_API_KEY                 (secret)
FUB_API_KEY                    (secret, must be account-owner key)
```

Required for some scripts / production:
```
FUB_CUSTOM_FIELD               = customSierraLoginURL
SIERRA_ORIGINATING_SYSTEM      = FUB-AutoLogin-Sync   (optional, but stored)
WEBHOOK_SECRET                 (random UUID; webhook only — Sierra sends X-Webhook-Secret header)
SIERRA_LOGIN_FIELD             (legacy, not actively used — URL is now constructed, not fetched)
```

Local dev: every script loads `.env` from its own folder via a tiny inline loader (no `python-dotenv` dependency). The `.env` is gitignored. In CI/production, env vars come from GitHub Actions secrets / Render env vars and the loader is a no-op.

---

## 8. Last known state (snapshot)

These numbers are from the most recent runs (May 2026) — refresh by running the count scripts before relying on them:

- **Sierra**: ~10,388 leads total (`probe_sierra.py` step 1).
- **FUB**: thousands of contacts; 1,958 carried the `Needs Sierra URL` tag; after `match_tagged_contacts.py --write --fallback-generic`, **1,954 were updated** (90 matched by email, 23 by phone, 1,841 got the generic `https://www.thevegasagent.com/?sentfrom=auto` fallback).
- **Tags pushed live**: `SPRIORITY` (98 leads), `2026 Daily Search Done` — see `tags_to_push.txt`.
- **Cron status**: both workflows wired to GitHub Actions; sync runs every 5 min, tag push every hour.
- **Webhook**: deployed at `https://sierra-fub-sync.onrender.com/sierra-webhook` (Render free tier).

---

## 9. Common pitfalls — read before you debug

1. **"Sierra returns the same leads no matter what page I ask for"** → you're using `page=`, must be `pageNumber=`. See §2.1(a).
2. **"FUB person has the right URL but the script keeps trying to write it"** → you forgot `fields=allFields` on the GET. Custom fields are dropped without it. See §3.2.
3. **"I added a tag to FUB and it wiped out the existing tags"** → `PUT /people/{id}` with `{"tags": [...]}` REPLACES. Must fetch + append + PUT full list. See §3.4.
4. **"Sierra filter for my tag returns ALL 10,388 leads"** → wrong query param. Must be `tags=` (plural). Anything else is silently ignored. See §2.3.
5. **"PUT to a template returns 400"** → you didn't strip read-only/stats fields. See §3.5.
6. **"Webhook returns 401"** → `X-Webhook-Secret` header from Sierra doesn't match `WEBHOOK_SECRET` in Render env. Realign them.
7. **"First webhook call hangs ~30 seconds"** → Render free tier cold start. Expected. Subsequent calls are instant for 15 minutes of activity.
8. **"Two tags exist with similar names"** → check `/leadTags` for variants. Real account has `S Priority` (1 lead) AND `SPRIORITY` (98 leads). Ask which one the user means before acting.
9. **"`AGENT_SUBDOMAINS` is wrong in production"** → it lives in TWO files (`sierra_fub_sync.py` and `webhook_handler.py`). Update both.

---

## 10. About session continuity (read this if context feels missing)

Claude Code on the web runs each session in a fresh container. Past sessions' transcripts are **not** available in new sessions — they were stored in their own containers which have been reclaimed. This file (`CLAUDE.md`) is the durable handoff. **When you learn something new that future sessions will need**, append it here and commit. That is the mechanism that prevents starting from scratch.

If the user mentions a previous session's finding that contradicts this file, trust the user and ask them to point you at the specific commit, PR, or output file from that session — and once verified, update this doc.
