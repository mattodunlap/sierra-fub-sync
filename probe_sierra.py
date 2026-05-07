"""
Diagnostic probe to find the right Sierra endpoint for fetching a single
lead's full details, including the auto-login URL.

Tries several URL patterns and HTTP methods, dumps every field on the
lead so we can spot the auto-login URL no matter what it's called.
"""

import os
import json
import requests
from pathlib import Path


def load_env():
    env_path = Path(__file__).parent / ".env"
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ[key.strip()] = value.strip().strip('"').strip("'")


load_env()

HEADERS = {
    "Sierra-ApiKey": os.environ["SIERRA_API_KEY"],
    "Sierra-OriginatingSystemName": os.environ.get(
        "SIERRA_ORIGINATING_SYSTEM", "FUB-AutoLogin-Sync"
    ),
    "Content-Type": "application/json",
}
BASE = "https://api.sierrainteractivedev.com"


def hr(label):
    print("\n" + "=" * 70)
    print(label)
    print("=" * 70)


# -------- Step 1: pull one lead from /leads/find and dump all its fields --------
hr("STEP 1 — Listing fields on a lead from /leads/find")
r = requests.get(f"{BASE}/leads/find", headers=HEADERS,
                 params={"page": 1, "pageSize": 1}, timeout=15)
print(f"Status: {r.status_code}")
data = r.json().get("data", {})
leads = data.get("leads", [])
if not leads:
    print("No leads returned, stopping.")
    raise SystemExit
lead = leads[0]
lead_id = lead.get("id")
print(f"Sample lead id: {lead_id}")
print(f"All fields on this lead (find listing):")
for k in sorted(lead.keys()):
    v = lead[k]
    if isinstance(v, str) and len(v) > 60:
        v = v[:60] + "..."
    print(f"  {k}: {v!r}")


# -------- Step 2: try multiple endpoint shapes for getting one lead --------
hr("STEP 2 — Probing endpoints to fetch a single lead's full detail")

attempts = [
    ("GET",    f"{BASE}/leads/get",          {"id": lead_id}, None),
    ("POST",   f"{BASE}/leads/get",          None,            {"id": lead_id}),
    ("GET",    f"{BASE}/leads/get/{lead_id}", None,           None),
    ("GET",    f"{BASE}/leads/{lead_id}",    None,            None),
    ("GET",    f"{BASE}/lead/get",           {"id": lead_id}, None),
    ("GET",    f"{BASE}/lead/{lead_id}",     None,            None),
    ("GET",    f"{BASE}/leads/details",      {"id": lead_id}, None),
    ("GET",    f"{BASE}/leads/find",         {"id": lead_id, "pageSize": 1}, None),
]

working = None
for method, url, params, body in attempts:
    try:
        r = requests.request(method, url, headers=HEADERS,
                             params=params, json=body, timeout=15)
        snippet = r.text[:120].replace("\n", " ")
        marker = "  OK" if r.status_code == 200 else "FAIL"
        print(f"{marker} {method:5} {url:60} -> {r.status_code}  {snippet}")
        if r.status_code == 200 and not working:
            working = (method, url, params, body, r)
    except Exception as e:
        print(f"FAIL {method:5} {url:60} -> {e}")


# -------- Step 3: if we found a working detail endpoint, dump its fields --------
if working:
    method, url, params, body, r = working
    hr(f"STEP 3 — Full detail from working endpoint: {method} {url}")
    detail = r.json()
    # Sierra wraps things in {success, data: {lead: {...}}}
    payload = detail.get("data", detail)
    if isinstance(payload, dict) and "lead" in payload:
        payload = payload["lead"]
    if isinstance(payload, dict):
        print(f"Keys on detail object ({len(payload)} total):")
        for k in sorted(payload.keys()):
            v = payload[k]
            if isinstance(v, str) and len(v) > 80:
                v = v[:80] + "..."
            elif isinstance(v, (dict, list)):
                v = f"<{type(v).__name__} with {len(v)} items>"
            print(f"  {k}: {v!r}")

        # Highlight any field whose value LOOKS like an auto-login URL
        print("\nFields whose value looks like a login URL:")
        any_url_found = False
        for k, v in payload.items():
            if isinstance(v, str) and v.startswith("http") and ("login" in v.lower() or "auto" in v.lower() or "token" in v.lower() or len(v) > 80):
                print(f"  {k} -> {v[:120]}")
                any_url_found = True
        if not any_url_found:
            print("  (none obvious — maybe Sierra returns the URL only in a separate endpoint)")
    else:
        print("Unexpected response shape:")
        print(json.dumps(detail, indent=2)[:2000])
else:
    print("\nNo /leads/get-style endpoint worked. We may need a different approach.")
