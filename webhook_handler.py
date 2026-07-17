"""
Sierra -> FUB auto-login URL sync (webhook / real-time version)

A FastAPI app that Sierra calls every time a new lead registers.
When a webhook fires, this looks the lead up in FUB and writes the
auto-login URL into the custom field within seconds.

Deployed on Fly.io (see fly.toml + Dockerfile, and DEPLOY.md for the runbook).
After deploy, give Sierra your public URL (e.g. https://sierra-fub-webhook.fly.dev/sierra-webhook)
in their webhook settings.

Required env vars:
    SIERRA_API_KEY               Sierra Direct API key (used to fetch full lead detail)
    FUB_API_KEY                  FUB API key (account owner)
    FUB_CUSTOM_FIELD             FUB custom field API name
    WEBHOOK_SECRET               Shared secret you set in Sierra; we verify it on each call
    SIERRA_ORIGINATING_SYSTEM    (optional) Name to send as Sierra-OriginatingSystemName

Run locally:
    pip install fastapi uvicorn requests
    uvicorn webhook_handler:app --reload --port 8000
"""

import os
import requests
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks

SIERRA_API_KEY = os.environ["SIERRA_API_KEY"]
FUB_API_KEY = os.environ["FUB_API_KEY"]
FUB_CUSTOM_FIELD = os.environ.get("FUB_CUSTOM_FIELD", "customSierraLoginURL")
SIERRA_ORIGINATING_SYSTEM = os.environ.get(
    "SIERRA_ORIGINATING_SYSTEM", "FUB-AutoLogin-Sync"
)
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")

SIERRA_BASE = "https://api.sierrainteractivedev.com"
FUB_BASE = "https://api.followupboss.com/v1"

SIERRA_HEADERS = {
    "Sierra-ApiKey": SIERRA_API_KEY,
    "Sierra-OriginatingSystemName": SIERRA_ORIGINATING_SYSTEM,
}

# Optional FUB registered-system headers (X-System / X-System-Key).
# Set FUB_SYSTEM + FUB_SYSTEM_KEY as Fly secrets to identify this
# integration to FUB; harmless to omit.
FUB_HEADERS = {}
if os.environ.get("FUB_SYSTEM"):
    FUB_HEADERS["X-System"] = os.environ["FUB_SYSTEM"]
if os.environ.get("FUB_SYSTEM_KEY"):
    FUB_HEADERS["X-System-Key"] = os.environ["FUB_SYSTEM_KEY"]

AGENT_SUBDOMAINS = {
    "matthew": "www",
    "adrianne": "adrianne",
}
DEFAULT_SUBDOMAIN = "www"
SITE_DOMAIN = "thevegasagent.com"

# Agent-jump-in URL — for Matthew/Adrianne to land in a client's Sierra
# admin portal in one click. Distinct from client-side auto-login URL.
SIERRA_ADMIN_BASE = "https://client3.sierrainteractivedev.com/lead-detail.aspx"
FUB_AGENT_LINK_FIELD = "customSierraAgentLoginLink"

# Filtered saved-search URL (the per-search deep-link used in emails so the
# lead lands on THEIR list, not the homepage). Populated if Sierra returns a
# primary savedSearchId for the lead. Field added 2026-05-27.
FUB_SEARCH_URL_FIELD = "customSierraSearchURL"
FUB_ADMIN_URL_FIELD  = "customSierraAdminURL"

app = FastAPI()


def build_login_url(lead):
    """Client-side auto-login URL → drops them on thevegasagent.com homepage."""
    assigned = lead.get("assignedTo") or {}
    first_name = (assigned.get("agentUserFirstName") or "").lower().strip()
    subdomain = AGENT_SUBDOMAINS.get(first_name, DEFAULT_SUBDOMAIN)
    lead_id = lead.get("id")
    if not lead_id:
        return None
    return f"https://{subdomain}.{SITE_DOMAIN}/?userid={lead_id}&sentfrom=auto"


def build_agent_login_url(lead):
    """Agent-jump-in URL → Matthew/Adrianne click into the lead's Sierra admin portal."""
    lead_id = lead.get("id")
    if not lead_id:
        return None
    return f"{SIERRA_ADMIN_BASE}?id={lead_id}"


def build_search_url(lead):
    """Filtered saved-search deep-link. Queries Sierra for the lead's primary
    saved search; returns None if they have none yet."""
    lead_id = lead.get("id")
    if not lead_id:
        return None
    try:
        r = requests.get(f"{SIERRA_BASE}/savedSearches/find",
                         headers=SIERRA_HEADERS,
                         params={"leadId": lead_id}, timeout=10)
        if r.status_code != 200:
            return None
        data = r.json().get("data", {})
        searches = data.get("savedSearches", []) if isinstance(data, dict) else []
        if not searches:
            return None
        search_id = searches[0].get("searchId")
        if not search_id:
            return None
        # Match the URL shape send_1000_morning expects (searchtype=2&searchid=N)
        assigned = lead.get("assignedTo") or {}
        first_name = (assigned.get("agentUserFirstName") or "").lower().strip()
        subdomain = AGENT_SUBDOMAINS.get(first_name, DEFAULT_SUBDOMAIN)
        return (f"https://{subdomain}.{SITE_DOMAIN}/property-search/results/"
                f"?searchtype=2&searchid={search_id}&userid={lead_id}&sentfrom=auto")
    except Exception:
        return None


def get_sierra_lead(lead_id):
    """Fetch a single lead's full detail from Sierra."""
    r = requests.get(
        f"{SIERRA_BASE}/leads/get/{lead_id}",
        headers=SIERRA_HEADERS,
        timeout=15,
    )
    r.raise_for_status()
    payload = r.json().get("data", {})
    if isinstance(payload, dict) and "lead" in payload:
        return payload["lead"]
    return payload


def find_fub_person(email):
    r = requests.get(
        f"{FUB_BASE}/people",
        auth=(FUB_API_KEY, ""),
        headers=FUB_HEADERS,
        params={"email": email, "fields": "allFields"},
        timeout=15,
    )
    if r.status_code != 200:
        return None
    people = r.json().get("people", [])
    return people[0] if people else None


def create_fub_person(email, first_name, last_name, login_url,
                       agent_url=None, search_url=None, admin_url=None):
    """Field consolidation 2026-05-28 per Matthew: only customSierraSearchURL
    (filtered auto-login) and customSierraAdminURL (agent jump-in) are kept.
    Legacy login_url and agent_url params accepted but no longer written."""
    payload = {
        "emails": [{"value": email}],
        "firstName": first_name or "",
        "lastName": last_name or "",
        "source": "Sierra Interactive",
    }
    # Use the filtered search URL as the primary lead-facing link.
    # If no filtered search exists yet, fall back to login_url so the lead
    # still has SOME URL on their record.
    payload[FUB_SEARCH_URL_FIELD] = search_url or login_url or ''
    if admin_url:  payload[FUB_ADMIN_URL_FIELD] = admin_url
    r = requests.post(
        f"{FUB_BASE}/people",
        auth=(FUB_API_KEY, ""),
        headers=FUB_HEADERS,
        json=payload,
        timeout=15,
    )
    return r.status_code in (200, 201)


def update_fub_person(person_id, login_url, agent_url=None,
                      search_url=None, admin_url=None):
    """Field consolidation 2026-05-28: write only the 2 keeper fields."""
    fields = {}
    fields[FUB_SEARCH_URL_FIELD] = search_url or login_url or ''
    if admin_url: fields[FUB_ADMIN_URL_FIELD] = admin_url
    r = requests.put(
        f"{FUB_BASE}/people/{person_id}",
        auth=(FUB_API_KEY, ""),
        headers=FUB_HEADERS,
        json=fields,
        timeout=15,
    )
    return r.status_code == 200


@app.get("/")
def health():
    return {"status": "ok"}


def process_lead(lead_id):
    """Full Sierra fetch + FUB write. Runs AFTER the webhook is acknowledged —
    Sierra silently bans a subscription after 4 slow/failed deliveries, so the
    request handler must never wait on these API calls."""
    lead = get_sierra_lead(lead_id)
    email = lead.get("email")
    login_url  = build_login_url(lead)
    agent_url  = build_agent_login_url(lead)
    search_url = build_search_url(lead)
    admin_url  = f"{SIERRA_ADMIN_BASE}?id={lead_id}"

    if not email or not login_url:
        print(f"lead {lead_id}: skipped (missing email or login url)")
        return

    person = find_fub_person(email)
    if person:
        ok = update_fub_person(person["id"], login_url,
                               agent_url=agent_url, search_url=search_url,
                               admin_url=admin_url)
        print(f"lead {lead_id}: updated person {person['id']} ok={ok} "
              f"search_url={bool(search_url)}")
    else:
        ok = create_fub_person(
            email=email,
            first_name=lead.get("firstName"),
            last_name=lead.get("lastName"),
            login_url=login_url,
            agent_url=agent_url,
            search_url=search_url,
            admin_url=admin_url,
        )
        print(f"lead {lead_id}: created person ok={ok} "
              f"search_url={bool(search_url)}")


@app.post("/sierra-webhook")
async def sierra_webhook(request: Request, background_tasks: BackgroundTasks):
    if WEBHOOK_SECRET:
        # Sierra's API-based webhook registration can't attach custom headers,
        # so the secret may arrive as a ?secret= query param instead.
        provided = request.headers.get("X-Webhook-Secret", "")
        provided_qs = request.query_params.get("secret", "")
        if WEBHOOK_SECRET not in (provided, provided_qs):
            raise HTTPException(status_code=401, detail="Bad secret")

    payload = await request.json()
    lead_id = (
        payload.get("leadId")
        or payload.get("id")
        or (payload.get("data") or {}).get("leadId")
    )
    if not lead_id:
        return {"ignored": "no lead id"}

    # Acknowledge immediately; do the Sierra/FUB round-trips in the background.
    background_tasks.add_task(process_lead_safe, lead_id)
    return {"accepted": True, "lead_id": lead_id}


def process_lead_safe(lead_id):
    """If processing fails, the every-5-min polling sync (GitHub Actions)
    catches the lead on its next pass — log and move on."""
    try:
        process_lead(lead_id)
    except Exception as e:
        print(f"lead {lead_id}: processing failed ({e!r}); polling sync will catch it")
