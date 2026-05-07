"""
Sierra -> FUB auto-login URL sync (webhook / real-time version)

A FastAPI app that Sierra calls every time a new lead registers.
When a webhook fires, this looks the lead up in FUB and writes the
auto-login URL into the custom field within seconds.

Deploy on Render (free), Railway, Fly.io, or any host that runs Python.
After deploy, give Sierra your public URL (e.g. https://yourapp.onrender.com/sierra-webhook)
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
from fastapi import FastAPI, Request, HTTPException

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

AGENT_SUBDOMAINS = {
    "matthew": "www",
    "adrianne": "adrianne",
}
DEFAULT_SUBDOMAIN = "www"
SITE_DOMAIN = "thevegasagent.com"

app = FastAPI()


def build_login_url(lead):
    assigned = lead.get("assignedTo") or {}
    first_name = (assigned.get("agentUserFirstName") or "").lower().strip()
    subdomain = AGENT_SUBDOMAINS.get(first_name, DEFAULT_SUBDOMAIN)
    lead_id = lead.get("id")
    if not lead_id:
        return None
    return f"https://{subdomain}.{SITE_DOMAIN}/?userid={lead_id}&sentfrom=auto"


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
        params={"email": email, "fields": "allFields"},
        timeout=15,
    )
    if r.status_code != 200:
        return None
    people = r.json().get("people", [])
    return people[0] if people else None


def create_fub_person(email, first_name, last_name, login_url):
    """If the contact doesn't exist in FUB yet, create them with the URL set."""
    payload = {
        "emails": [{"value": email}],
        "firstName": first_name or "",
        "lastName": last_name or "",
        "source": "Sierra Interactive",
        FUB_CUSTOM_FIELD: login_url,
    }
    r = requests.post(
        f"{FUB_BASE}/people",
        auth=(FUB_API_KEY, ""),
        json=payload,
        timeout=15,
    )
    return r.status_code in (200, 201)


def update_fub_person(person_id, login_url):
    r = requests.put(
        f"{FUB_BASE}/people/{person_id}",
        auth=(FUB_API_KEY, ""),
        json={FUB_CUSTOM_FIELD: login_url},
        timeout=15,
    )
    return r.status_code == 200


@app.get("/")
def health():
    return {"status": "ok"}


@app.post("/sierra-webhook")
async def sierra_webhook(request: Request):
    if WEBHOOK_SECRET:
        provided = request.headers.get("X-Webhook-Secret", "")
        if provided != WEBHOOK_SECRET:
            raise HTTPException(status_code=401, detail="Bad secret")

    payload = await request.json()
    lead_id = (
        payload.get("leadId")
        or payload.get("id")
        or (payload.get("data") or {}).get("leadId")
    )
    if not lead_id:
        return {"ignored": "no lead id"}

    lead = get_sierra_lead(lead_id)
    email = lead.get("email")
    login_url = build_login_url(lead)

    if not email or not login_url:
        return {"ignored": "missing email or login url", "lead_id": lead_id}

    person = find_fub_person(email)
    if person:
        ok = update_fub_person(person["id"], login_url)
        return {"action": "updated", "ok": ok, "person_id": person["id"]}
    else:
        ok = create_fub_person(
            email=email,
            first_name=lead.get("firstName"),
            last_name=lead.get("lastName"),
            login_url=login_url,
        )
        return {"action": "created", "ok": ok}
